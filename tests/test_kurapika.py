"""Tests for the kurapika CLI. Standard library only.

Run: python3 -m unittest discover -s tests
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import kurapika  # noqa: E402


class KurapikaTestCase(unittest.TestCase):
    lang = "ja"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.vault = base / "vault"
        self.config = base / "config"
        self._env = mock.patch.dict(os.environ, {"KURAPIKA_CONFIG_DIR": str(self.config)})
        self._env.start()
        self.run_cli("init", str(self.vault), "--create", "--lang", self.lang)

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def run_cli(self, *argv, stdin="", expect=0):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(stdin)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = kurapika.main(list(argv))
        self.assertEqual(code, expect, msg=err.getvalue())
        text = out.getvalue() if expect == 0 else err.getvalue()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def summary(self, name):
        return (self.vault / name / "summary.md").read_text(encoding="utf-8")


class TopicTests(KurapikaTestCase):
    def test_new_topic_keeps_japanese_name_and_creates_only_summary(self):
        result = self.run_cli("topic", "new", "--title", "認証まわり調査")
        self.assertEqual(result["name"], "認証まわり調査")
        self.assertTrue(result["uri"].startswith("obsidian://open?path="))
        files = sorted(p.name for p in (self.vault / "認証まわり調査").iterdir())
        self.assertEqual(files, ["summary.md"])  # ADR/ISSUE folders are created lazily
        text = self.summary("認証まわり調査")
        for headings in kurapika.SECTIONS.values():
            self.assertIn("## " + headings["ja"], text)
        self.assertIn("トピックを作成", kurapika.get_section(text, "history"))

    def test_new_topic_is_idempotent(self):
        self.run_cli("topic", "new", "--title", "foo")
        self.assertFalse(self.run_cli("topic", "new", "--title", "foo")["created"])

    def test_unsafe_characters_are_replaced(self):
        self.assertEqual(kurapika.safe_name("a/b: c?  [d]"), "a-b-c-d")
        self.run_cli("topic", "new", "--title", "///", expect=1)
        self.run_cli("topic", "new", "--title", "knowledge", expect=1)

    def test_note_append_and_replace_logs_history(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.run_cli("note", "auth", "research", stdin="Cookie セッションを調査\n```bash\n# comment\n```\n")
        self.run_cli("note", "auth", "direction", stdin="JWT に寄せる")
        self.run_cli("note", "auth", "direction", stdin="OAuth に寄せる")
        text = self.summary("auth")
        research = kurapika.get_section(text, "research")
        self.assertIn("Cookie セッションを調査", research)
        self.assertIn("# comment", research)  # a code-fence comment does not end the section
        self.assertEqual(kurapika.get_section(text, "direction"), "OAuth に寄せる")
        history = kurapika.get_section(text, "history")
        self.assertIn("旧: JWT に寄せる", history)
        self.assertNotIn("bak", " ".join(p.name for p in (self.vault / "auth").iterdir()))

    def test_history_section_is_append_only(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.run_cli("note", "auth", "history", "--mode", "replace", stdin="x", expect=1)
        self.run_cli("note", "auth", "now", stdin="", expect=1)

    def test_show_returns_recent_history_newest_first(self):
        self.run_cli("topic", "new", "--title", "auth")
        for i in range(7):
            self.run_cli("note", "auth", "history", stdin=f"step {i}")
        shown = self.run_cli("topic", "show", "auth", "--history", "3")
        self.assertEqual(len(shown["history_recent"]), 3)
        self.assertTrue(shown["history_recent"][0].endswith("step 6"))
        self.assertEqual(shown["history_total"], 8)

    def test_resolve_topic_by_partial_name(self):
        self.run_cli("topic", "new", "--title", "認証まわり調査")
        self.run_cli("topic", "new", "--title", "決済の改修")
        self.assertEqual(self.run_cli("topic", "show", "認証")["name"], "認証まわり調査")
        self.run_cli("topic", "show", "存在しない", expect=1)

    def test_status_change_is_logged_and_hidden_from_default_list(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.run_cli("topic", "status", "auth", "done")
        self.assertIn("進行中 → 完了", kurapika.get_section(self.summary("auth"), "history"))
        self.assertEqual(self.run_cli("topic", "list"), [])
        self.assertEqual(len(self.run_cli("topic", "list", "--all")), 1)


class AdrIssueTests(KurapikaTestCase):
    def test_adr_and_issue_are_numbered_and_linked(self):
        self.run_cli("topic", "new", "--title", "auth")
        adr = self.run_cli("adr", "new", "--topic", "auth", "--title", "JWT を採用")
        self.assertEqual(adr["file"], "auth/ADR/ADR-0001-JWT-を採用.md")
        second = self.run_cli("adr", "new", "--topic", "auth", "--title", "鍵の保管")
        self.assertTrue(second["file"].startswith("auth/ADR/ADR-0002-"))
        issue = self.run_cli("issue", "new", "--topic", "auth", "--title", "リフレッシュ方式", "--adr-ref", "ADR-0001-JWT-を採用.md")
        issue_text = (self.vault / issue["file"]).read_text(encoding="utf-8")
        self.assertIn('adr_refs: ["ADR-0001-JWT-を採用.md"]', issue_text)

        text = self.summary("auth")
        self.assertIn("[[auth/ADR/ADR-0001-JWT-を採用|ADR-0001: JWT を採用]]", kurapika.get_section(text, "decisions"))
        self.assertIn("ISSUE-0001", kurapika.get_section(text, "issues"))
        shown = self.run_cli("topic", "show", "auth")
        self.assertEqual([a["status"] for a in shown["adrs"]], ["accepted", "accepted"])
        self.assertEqual(shown["issues"][0]["status"], "open")

    def test_adr_requires_existing_topic(self):
        self.run_cli("adr", "new", "--topic", "nope", "--title", "x", expect=1)


class SearchTests(KurapikaTestCase):
    def test_multi_term_search_with_snippets_and_scope(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.run_cli("note", "auth", "research", stdin="JWT の有効期限は 15 分")
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "JWT.md").write_text("JWT", encoding="utf-8")
        (self.vault / "my-own-note.md").write_text("JWT", encoding="utf-8")
        results = self.run_cli("search", "jwt 有効期限")
        self.assertEqual([r["path"] for r in results], ["auth/summary.md"])
        self.assertIn("有効期限", results[0]["snippets"][0])
        self.assertEqual(results[0]["kind"], "summary")


class CloseTests(KurapikaTestCase):
    def test_close_previews_then_moves_digest_to_knowledge(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.run_cli("adr", "new", "--topic", "auth", "--title", "JWT")
        preview = self.run_cli("topic", "close", "auth")
        self.assertIn("auth/summary.md", preview["would_delete"])
        self.assertTrue((self.vault / "auth").exists())

        self.run_cli("topic", "close", "auth", "--confirm", expect=1)  # empty body refused
        self.assertTrue((self.vault / "auth").exists())

        result = self.run_cli("topic", "close", "auth", "--confirm", stdin="## 結論\n\nJWT にした")
        self.assertEqual(result["knowledge_path"], "knowledge/auth.md")
        self.assertFalse((self.vault / "auth").exists())
        knowledge = (self.vault / "knowledge" / "auth.md").read_text(encoding="utf-8")
        self.assertIn("# auth", knowledge)
        self.assertIn("JWT にした", knowledge)
        index = (self.vault / "index.md").read_text(encoding="utf-8")
        self.assertIn("[[knowledge/auth|auth]]", index)

        self.run_cli("topic", "new", "--title", "auth")
        again = self.run_cli("topic", "close", "auth", "--confirm", stdin="second")
        self.assertEqual(again["knowledge_path"], "knowledge/auth-2.md")
        searched = self.run_cli("search", "JWT")
        self.assertEqual(searched[0]["kind"], "knowledge")


class CleanupTests(KurapikaTestCase):
    def test_cleanup_only_touches_managed_files(self):
        self.run_cli("topic", "new", "--title", "auth")
        (self.vault / "auth" / "ADR").mkdir()
        (self.vault / "auth" / "summary.md.bak").write_text("old", encoding="utf-8")
        (self.vault / ".kurapika.lock").write_text("", encoding="utf-8")
        (self.vault / "user-folder").mkdir()
        (self.vault / "user.md.bak").write_text("keep", encoding="utf-8")

        result = self.run_cli("cleanup")
        self.assertCountEqual(result["removed"], ["auth/ADR/", "auth/summary.md.bak", ".kurapika.lock"])
        self.assertTrue((self.vault / "user-folder").is_dir())
        self.assertTrue((self.vault / "user.md.bak").exists())
        self.assertEqual(self.run_cli("cleanup")["index"], "unchanged")

    def test_foreign_index_is_never_overwritten(self):
        (self.vault / "index.md").write_text("# my own index\n", encoding="utf-8")
        self.run_cli("topic", "new", "--title", "auth")
        self.assertEqual((self.vault / "index.md").read_text(encoding="utf-8"), "# my own index\n")
        self.assertEqual(self.run_cli("cleanup")["index"], "conflict")
        self.assertEqual(self.run_cli("organize-report")["index"], "conflict")


class OrganizeTests(KurapikaTestCase):
    def test_report_finds_stale_topics_broken_links_and_unknown_folders(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.run_cli("note", "auth", "research", stdin="see [[auth/ADR/ADR-0009-missing]]")
        old = 1_600_000_000
        for p in (self.vault / "auth").rglob("*"):
            os.utime(p, (old, old))
        (self.vault / "legacy-project").mkdir()
        report = self.run_cli("organize-report")
        self.assertEqual(report["stale_topics"][0]["name"], "auth")
        self.assertEqual(report["broken_links"][0]["link"], "auth/ADR/ADR-0009-missing")
        self.assertEqual(report["folders_without_summary"], ["legacy-project"])


class HookTests(KurapikaTestCase):
    def hook_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(kurapika.main(["hook", "session-start"]), 0)
        return out.getvalue()

    def test_hook_lists_active_topics_with_summary_and_now(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.run_cli("note", "auth", "oneline", stdin="社内 API の認証方式を決める")
        self.run_cli("note", "auth", "now", stdin="リフレッシュ方式を調査中")
        self.run_cli("topic", "new", "--title", "old")
        self.run_cli("topic", "status", "old", "done")
        output = self.hook_output()
        self.assertIn("進行中のトピック（1件）", output)
        self.assertIn("社内 API の認証方式を決める ｜ リフレッシュ方式を調査中", output)
        self.assertNotIn("- old", output)

    def test_hook_when_unconfigured(self):
        self.run_cli("config", "clear", "--confirm")
        self.assertIn("/obsidian-init", self.hook_output())

    def test_hook_nudges_organize_after_interval(self):
        self.run_cli("topic", "new", "--title", "auth")
        kurapika.save_state(last_organize="2000-01-01T00:00:00+00:00")
        self.assertIn("前回の整理から", self.hook_output())


class EnglishTests(KurapikaTestCase):
    lang = "en"

    def test_english_headings_and_cross_language_matching(self):
        self.run_cli("topic", "new", "--title", "auth")
        self.assertIn("## Research", self.summary("auth"))
        self.run_cli("config", "lang", "ja")
        self.run_cli("note", "auth", "research", stdin="works across languages")
        text = self.summary("auth")
        self.assertIn("works across languages", kurapika.get_section(text, "research"))
        self.assertNotIn("## 調べたこと", text)  # the existing English heading is reused


class SafetyRegressionTests(KurapikaTestCase):
    """One test per finding from the pre-1.0 review."""

    def test_reserved_names_are_rejected_case_insensitively(self):
        for title in ("Knowledge", "KNOWLEDGE", "index.md", "Index.MD"):
            self.run_cli("topic", "new", "--title", title, expect=1)

    def test_destructive_commands_need_an_exact_name(self):
        self.run_cli("topic", "new", "--title", "認証")
        self.run_cli("topic", "new", "--title", "認証基盤")
        self.run_cli("topic", "close", "認証", "--confirm", stdin="digest")
        err = self.run_cli("topic", "close", "認証", "--confirm", stdin="digest", expect=1)
        self.assertEqual(err["error"], "topic_not_found")
        self.assertTrue((self.vault / "認証基盤").is_dir())
        self.run_cli("topic", "close", "", "--confirm", stdin="digest", expect=1)
        self.run_cli("note", "基盤", "now", stdin="x", expect=1)
        self.assertEqual(self.run_cli("topic", "show", "基盤")["name"], "認証基盤")  # read-only partial is fine

    def test_folder_name_beats_title(self):
        self.run_cli("topic", "new", "--title", "b")
        self.run_cli("topic", "new", "--title", "a-old")
        path = self.vault / "a-old" / "summary.md"
        path.write_text(path.read_text(encoding="utf-8").replace("# a-old", "# b"), encoding="utf-8")
        self.assertEqual(self.run_cli("topic", "show", "b")["name"], "b")

    def test_unclosed_fence_does_not_swallow_other_sections(self):
        self.run_cli("topic", "new", "--title", "t")
        self.run_cli("note", "t", "oneline", stdin="コード:\n```bash\nls\n")
        self.run_cli("note", "t", "research", stdin="調査1")
        self.run_cli("note", "t", "oneline", stdin="新しい一言")
        text = self.summary("t")
        self.assertIn("調査1", kurapika.get_section(text, "research"))
        self.assertEqual(text.count("## 調べたこと"), 1)
        self.assertIn("トピックを作成", kurapika.get_section(text, "history"))
        self.assertEqual(kurapika.get_section(text, "oneline"), "新しい一言")

    def test_tags_are_not_headings_and_user_headings_are_demoted(self):
        self.run_cli("topic", "new", "--title", "t")
        self.run_cli("note", "t", "now", stdin="step1\n#todo\nstep2-old\n## 自分の見出し")
        self.assertIn("### 自分の見出し", self.summary("t"))
        self.run_cli("note", "t", "now", stdin="new-now")
        self.assertEqual(kurapika.get_section(self.summary("t"), "now"), "new-now")

    def test_user_folder_with_summary_is_not_a_topic(self):
        own = self.vault / "会議メモ"
        (own / "空フォルダ").mkdir(parents=True)
        (own / "summary.md").write_text("# 会議メモ\n", encoding="utf-8")
        (own / "old.md.bak").write_text("x", encoding="utf-8")
        self.assertEqual(self.run_cli("cleanup")["removed"], [])
        self.assertTrue((own / "空フォルダ").is_dir())
        self.assertEqual(self.run_cli("topic", "new", "--title", "会議メモ", expect=1)["error"], "folder_exists")
        self.assertEqual(self.run_cli("organize-report")["folders_without_summary"], ["会議メモ"])

    def test_symlinked_folder_outside_the_vault_is_ignored(self):
        outside = Path(self._tmp.name) / "outside"
        self.run_cli("topic", "new", "--title", "real")
        import shutil
        shutil.copytree(self.vault / "real", outside)
        (outside / "sub").mkdir()
        (outside / "keep.md.bak").write_text("x", encoding="utf-8")
        (self.vault / "ext").symlink_to(outside, target_is_directory=True)
        self.run_cli("cleanup")
        self.assertTrue((outside / "sub").is_dir())
        self.assertTrue((outside / "keep.md.bak").exists())
        self.run_cli("topic", "close", "ext", "--confirm", stdin="x", expect=1)
        self.assertTrue((outside / "summary.md").exists())

    def test_non_utf8_file_does_not_break_everything(self):
        bad = self.vault / "sj"
        bad.mkdir()
        (bad / "summary.md").write_bytes("---\ntype: topic\n---\n# 日本語".encode("shift_jis"))
        self.run_cli("topic", "new", "--title", "good")
        self.assertEqual([t["name"] for t in self.run_cli("topic", "list")], ["good"])
        self.run_cli("search", "日本語")
        self.run_cli("organize-report")

    def test_status_change_adds_missing_front_matter(self):
        self.run_cli("topic", "new", "--title", "t")
        path = self.vault / "t" / "summary.md"
        self.assertEqual(kurapika.parse_front_matter(kurapika.set_front_matter("# x\n", "status", "done")), {"status": "done"})
        self.run_cli("topic", "status", "t", "done")
        self.assertEqual(kurapika.parse_front_matter(path.read_text(encoding="utf-8"))["status"], "done")

    def test_interrupted_close_leftover_is_cleaned(self):
        (self.vault / (kurapika.CLOSING_PREFIX + "x")).mkdir()
        self.assertIn(kurapika.CLOSING_PREFIX + "x/", self.run_cli("cleanup")["removed"])


class TemplateTests(unittest.TestCase):
    def test_every_language_has_every_template_and_section(self):
        for lang in kurapika.LANGS:
            for name in ("summary.md", "adr.md", "issue.md", "knowledge.md"):
                self.assertTrue((kurapika.TEMPLATES_DIR / lang / name).is_file(), f"{lang}/{name}")
            summary = (kurapika.TEMPLATES_DIR / lang / "summary.md").read_text(encoding="utf-8")
            for headings in kurapika.SECTIONS.values():
                self.assertIn("## " + headings[lang], summary)
            self.assertIn(lang, kurapika.MESSAGES)
            self.assertEqual(set(kurapika.MESSAGES[lang]), set(kurapika.MESSAGES["en"]))


if __name__ == "__main__":
    unittest.main()
