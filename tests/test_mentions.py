"""Unit tests for the @mention parser and notification dispatcher."""
from __future__ import annotations

from opensoar.comments.mentions import parse_mention_tokens
from opensoar.notifications import (
    MentionNotification,
    clear_notification_hooks,
    dispatch_mention_notifications,
    register_notification_hook,
)


class TestParseMentionTokens:
    def test_extracts_single_mention(self):
        assert parse_mention_tokens("hello @alice") == ["alice"]

    def test_extracts_multiple_mentions(self):
        assert parse_mention_tokens("ping @alice and @bob") == ["alice", "bob"]

    def test_deduplicates_repeated_mentions(self):
        assert parse_mention_tokens("@alice @alice @alice") == ["alice"]

    def test_preserves_insertion_order(self):
        assert parse_mention_tokens("@charlie @alice @bob @alice") == [
            "charlie",
            "alice",
            "bob",
        ]

    def test_normalizes_to_lowercase(self):
        assert parse_mention_tokens("hey @Alice and @BOB") == ["alice", "bob"]

    def test_allows_underscore_dot_dash_digits(self):
        text = "cc @sec.ops @dr_who @a-team @user2"
        assert parse_mention_tokens(text) == ["sec.ops", "dr_who", "a-team", "user2"]

    def test_ignores_email_addresses(self):
        # The "@" following a word character should not match.
        assert parse_mention_tokens("mail alice@example.com please") == []

    def test_empty_and_none_safe(self):
        assert parse_mention_tokens("") == []
        assert parse_mention_tokens(None) == []  # type: ignore[arg-type]

    def test_lone_at_sign_is_not_a_mention(self):
        assert parse_mention_tokens("look @ this") == []

    def test_trailing_punctuation_is_stripped(self):
        assert parse_mention_tokens("hey @alice, @bob!") == ["alice", "bob"]


class TestNotificationHooks:
    def setup_method(self):
        clear_notification_hooks()

    def teardown_method(self):
        clear_notification_hooks()

    async def test_hook_fires_once_per_mention(self):
        captured: list[MentionNotification] = []

        async def hook(notification: MentionNotification) -> None:
            captured.append(notification)

        register_notification_hook(hook)

        await dispatch_mention_notifications(
            [
                MentionNotification(
                    recipient_username="alice",
                    recipient_id=None,
                    actor_username="charlie",
                    resource_type="alert",
                    resource_id="abc",
                    comment_id="c1",
                    comment_text="hey @alice",
                ),
                MentionNotification(
                    recipient_username="bob",
                    recipient_id=None,
                    actor_username="charlie",
                    resource_type="alert",
                    resource_id="abc",
                    comment_id="c1",
                    comment_text="hey @bob",
                ),
            ]
        )

        assert [n.recipient_username for n in captured] == ["alice", "bob"]

    async def test_sync_hook_is_supported(self):
        captured: list[MentionNotification] = []

        def hook(notification: MentionNotification) -> None:
            captured.append(notification)

        register_notification_hook(hook)

        await dispatch_mention_notifications(
            [
                MentionNotification(
                    recipient_username="alice",
                    recipient_id=None,
                    actor_username="charlie",
                    resource_type="incident",
                    resource_id="i1",
                    comment_id="c2",
                    comment_text="@alice look",
                )
            ]
        )
        assert len(captured) == 1
