import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from industry_radar.llm_client import call_deepseek_chat


class LlmClientTest(unittest.TestCase):
    def test_missing_api_key_raises_clear_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY is not set"):
                call_deepseek_chat([{"role": "user", "content": "hello"}])

    def test_request_does_not_print_api_key(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, _exc_type, _exc, _traceback) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {"choices": [{"message": {"content": '{"ok": true}'}}]}
                ).encode("utf-8")

        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

        output = io.StringIO()
        with patch("industry_radar.llm_client.urllib.request.urlopen", fake_urlopen):
            with redirect_stdout(output):
                content = call_deepseek_chat(
                    [{"role": "user", "content": "hello"}],
                    api_key="secret-key",
                    timeout=7,
                )

        self.assertEqual(content, '{"ok": true}')
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(captured["request"].headers["Authorization"], "Bearer secret-key")
        self.assertNotIn("secret-key", output.getvalue())


if __name__ == "__main__":
    unittest.main()
