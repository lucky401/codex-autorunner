from __future__ import annotations

import asyncio
import logging
from typing import Any, Sequence, Union

from ....core.logging_utils import log_event
from ....core.state import now_iso
from ..adapter import (
    QuestionCancelCallback,
    QuestionCustomCallback,
    QuestionDoneCallback,
    QuestionOptionCallback,
    TelegramCallbackQuery,
    TelegramMessage,
    build_question_keyboard,
)
from ..config import DEFAULT_APPROVAL_TIMEOUT_SECONDS
from ..types import PendingQuestion


def _extract_question_text(question: dict[str, Any]) -> str:
    for key in ("text", "prompt", "title", "label", "question"):
        value = question.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Question"


def _extract_question_options(question: dict[str, Any]) -> tuple[list[str], bool, bool]:
    multiple = bool(question.get("multiple"))
    custom = question.get("custom", True)
    for key in ("options", "choices"):
        raw = question.get(key)
        if isinstance(raw, list):
            options: list[str] = []
            for option in raw:
                if isinstance(option, str) and option.strip():
                    options.append(option.strip())
                    continue
                if isinstance(option, dict):
                    for label_key in ("label", "text", "value", "name", "id"):
                        value = option.get(label_key)
                        if isinstance(value, str) and value.strip():
                            options.append(value.strip())
                            break
            return options, multiple, custom
    return [], multiple, custom


def _format_question_prompt(question: dict[str, Any], *, index: int, total: int) -> str:
    title = _extract_question_text(question)
    if total > 1:
        prefix = f"Question {index + 1} of {total}"
    else:
        prefix = "Question"
    return f"{prefix}:\n{title}"


async def handle_custom_text_input(handlers: Any, message: TelegramMessage) -> bool:
    text = message.text or ""
    if not text:
        return False
    for request_id, pending in list(handlers._pending_questions.items()):
        if (
            pending.awaiting_custom_input
            and pending.chat_id == message.chat_id
            and (pending.thread_id is None or pending.thread_id == message.thread_id)
        ):
            handlers._pending_questions.pop(request_id, None)
            if not pending.future.done():
                pending.future.set_result(text)
            log_event(
                handlers._logger,
                logging.INFO,
                "telegram.question.custom_input",
                request_id=request_id,
                chat_id=message.chat_id,
                thread_id=message.thread_id,
                text_length=len(text),
            )
            if pending.message_id is not None:
                await handlers._edit_message_text(
                    pending.chat_id,
                    pending.message_id,
                    f"Selected: {text}",
                    reply_markup={"inline_keyboard": []},
                )
            await handlers._delete_message(message.chat_id, message.message_id)
            return True
    return False


class TelegramQuestionHandlers:
    async def _handle_question_request(
        self,
        *,
        request_id: str,
        turn_id: str,
        thread_id: str,
        questions: Sequence[dict[str, Any]],
    ) -> list[list[str]] | None:
        if not request_id or not turn_id:
            return None
        ctx = self._resolve_turn_context(turn_id, thread_id=thread_id)
        if ctx is None:
            return None
        if not questions:
            return None
        answers: list[list[str]] = []
        for index, question in enumerate(questions):
            options, multiple, custom = _extract_question_options(question)
            if not options:
                answers.append([])
                continue
            prompt = _format_question_prompt(
                question, index=index, total=len(questions)
            )
            try:
                keyboard = build_question_keyboard(
                    request_id,
                    question_index=index,
                    options=options,
                    multiple=multiple,
                    custom=custom,
                )
            except ValueError:
                log_event(
                    self._logger,
                    logging.WARNING,
                    "telegram.question.callback_too_long",
                    request_id=request_id,
                    question_index=index,
                )
                await self._send_message(
                    ctx.chat_id,
                    "Question prompt too long to send; answering as unanswered.",
                    thread_id=ctx.thread_id,
                    reply_to=ctx.reply_to_message_id,
                )
                answers.append([])
                continue
            payload_text, parse_mode = self._prepare_outgoing_text(
                prompt,
                chat_id=ctx.chat_id,
                thread_id=ctx.thread_id,
                reply_to=ctx.reply_to_message_id,
                topic_key=ctx.topic_key,
                codex_thread_id=ctx.codex_thread_id,
            )
            try:
                response = await self._bot.send_message(
                    ctx.chat_id,
                    payload_text,
                    message_thread_id=ctx.thread_id,
                    reply_to_message_id=ctx.reply_to_message_id,
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                )
            except Exception as exc:
                log_event(
                    self._logger,
                    logging.WARNING,
                    "telegram.question.send_failed",
                    request_id=request_id,
                    question_index=index,
                    chat_id=ctx.chat_id,
                    thread_id=ctx.thread_id,
                    exc=exc,
                )
                await self._send_message(
                    ctx.chat_id,
                    "Question prompt failed to send; rejecting question.",
                    thread_id=ctx.thread_id,
                    reply_to=ctx.reply_to_message_id,
                )
                return None
            message_id = (
                response.get("message_id") if isinstance(response, dict) else None
            )
            created_at = now_iso()
            loop = asyncio.get_running_loop()
            future: asyncio.Future[Union[list[int], str, None]] = loop.create_future()
            pending = PendingQuestion(
                request_id=request_id,
                turn_id=str(turn_id),
                codex_thread_id=thread_id,
                chat_id=ctx.chat_id,
                thread_id=ctx.thread_id,
                topic_key=ctx.topic_key,
                message_id=message_id if isinstance(message_id, int) else None,
                created_at=created_at,
                question_index=index,
                prompt=prompt,
                options=options,
                future=future,
                multiple=multiple,
                custom=custom,
                selected_indices=set(),
                awaiting_custom_input=False,
            )
            self._pending_questions[request_id] = pending
            self._touch_cache_timestamp("pending_questions", request_id)
            try:
                result = await asyncio.wait_for(
                    future, timeout=DEFAULT_APPROVAL_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                self._pending_questions.pop(request_id, None)
                log_event(
                    self._logger,
                    logging.WARNING,
                    "telegram.question.timeout",
                    request_id=request_id,
                    question_index=index,
                    chat_id=ctx.chat_id,
                    thread_id=ctx.thread_id,
                    timeout_seconds=DEFAULT_APPROVAL_TIMEOUT_SECONDS,
                )
                if pending.message_id is not None:
                    await self._edit_message_text(
                        pending.chat_id,
                        pending.message_id,
                        "Question timed out.",
                        reply_markup={"inline_keyboard": []},
                    )
                return None
            except asyncio.CancelledError:
                self._pending_questions.pop(request_id, None)
                raise
            if result is None:
                return None
            if isinstance(result, str):
                answers.append([result])
            else:
                selected_options = [options[i] for i in result if 0 <= i < len(options)]
                answers.append(selected_options)
        return answers

    async def _handle_question_callback(
        self,
        callback: TelegramCallbackQuery,
        parsed: (
            QuestionOptionCallback
            | QuestionDoneCallback
            | QuestionCustomCallback
            | QuestionCancelCallback
        ),
    ) -> None:
        pending = self._pending_questions.get(parsed.request_id)
        if pending is None:
            await self._answer_callback(callback, "Selection expired")
            return
        if pending.message_id is not None and callback.message_id != pending.message_id:
            await self._answer_callback(callback, "Selection expired")
            return
        if isinstance(parsed, QuestionCancelCallback):
            self._pending_questions.pop(parsed.request_id, None)
            if not pending.future.done():
                pending.future.set_result(None)
            log_event(
                self._logger,
                logging.INFO,
                "telegram.question.cancelled",
                request_id=parsed.request_id,
                chat_id=callback.chat_id,
                thread_id=callback.thread_id,
            )
            await self._answer_callback(callback, "Canceled")
            if pending.message_id is not None:
                await self._edit_message_text(
                    pending.chat_id,
                    pending.message_id,
                    "Question canceled.",
                    reply_markup={"inline_keyboard": []},
                )
            return
        if isinstance(parsed, QuestionCustomCallback):
            if not pending.custom:
                await self._answer_callback(callback, "Custom input disabled")
                return
            pending.awaiting_custom_input = True
            await self._answer_callback(callback, "Enter your answer below")
            await self._send_message(
                pending.chat_id,
                "Please type your custom answer:",
                thread_id=pending.thread_id,
            )
            return
        if isinstance(parsed, QuestionDoneCallback):
            if not pending.multiple:
                await self._answer_callback(callback, "Invalid for single-select")
                return
            if not pending.selected_indices:
                await self._answer_callback(callback, "No selections")
                return
            self._pending_questions.pop(parsed.request_id, None)
            if not pending.future.done():
                pending.future.set_result(list(pending.selected_indices))
            selections = ", ".join(pending.options[i] for i in pending.selected_indices)
            log_event(
                self._logger,
                logging.INFO,
                "telegram.question.done",
                request_id=parsed.request_id,
                question_index=pending.question_index,
                selections=selections,
                chat_id=callback.chat_id,
                thread_id=callback.thread_id,
            )
            await self._answer_callback(callback, "Done")
            if pending.message_id is not None:
                await self._edit_message_text(
                    pending.chat_id,
                    pending.message_id,
                    f"Selected: {selections}",
                    reply_markup={"inline_keyboard": []},
                )
            return
        if isinstance(parsed, QuestionOptionCallback):
            if parsed.question_index != pending.question_index:
                await self._answer_callback(callback, "Selection expired")
                return
            if parsed.option_index < 0 or parsed.option_index >= len(pending.options):
                await self._answer_callback(callback, "Invalid selection")
                return
            if not pending.multiple:
                self._pending_questions.pop(parsed.request_id, None)
                if not pending.future.done():
                    pending.future.set_result([parsed.option_index])
                log_event(
                    self._logger,
                    logging.INFO,
                    "telegram.question.selected",
                    request_id=parsed.request_id,
                    question_index=parsed.question_index,
                    option_index=parsed.option_index,
                    chat_id=callback.chat_id,
                    thread_id=callback.thread_id,
                )
                await self._answer_callback(callback, "Selected")
                if pending.message_id is not None:
                    selection = pending.options[parsed.option_index]
                    await self._edit_message_text(
                        pending.chat_id,
                        pending.message_id,
                        f"Selected: {selection}",
                        reply_markup={"inline_keyboard": []},
                    )
                return
            if parsed.option_index in pending.selected_indices:
                pending.selected_indices.remove(parsed.option_index)
                display_msg = "Deselected"
            else:
                pending.selected_indices.add(parsed.option_index)
                display_msg = "Selected"
            updated_keyboard = build_question_keyboard(
                parsed.request_id,
                question_index=pending.question_index,
                options=pending.options,
                multiple=pending.multiple,
                custom=pending.custom,
                selected_indices=pending.selected_indices,
                include_cancel=True,
            )
            log_event(
                self._logger,
                logging.INFO,
                "telegram.question.toggle",
                request_id=parsed.request_id,
                question_index=parsed.question_index,
                option_index=parsed.option_index,
                selected=parsed.option_index in pending.selected_indices,
                chat_id=callback.chat_id,
                thread_id=callback.thread_id,
            )
            await self._answer_callback(callback, display_msg)
            if pending.message_id is not None:
                selections = ", ".join(
                    pending.options[i] for i in pending.selected_indices
                )
                new_prompt = f"{pending.prompt}\n\nSelected: {selections or 'None'}"
                await self._edit_message_text(
                    pending.chat_id,
                    pending.message_id,
                    new_prompt,
                    reply_markup=updated_keyboard,
                )
            return
