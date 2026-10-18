import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AdvisorVoiceUITests(unittest.TestCase):
    def test_app_keeps_five_tabs_and_text_advisor_with_voice_controls(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
        self.assertEqual(len(app.exception), 0, [error.message for error in app.exception])
        self.assertEqual(len(app.tabs), 5)
        self.assertTrue(any(field.label == "Question" for field in app.text_area))
        self.assertTrue(any(button.label.startswith("Transcribe audio") for button in app.button))

    def test_transcribe_without_audio_shows_recoverable_warning(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
        transcribe = next(button for button in app.button if button.label.startswith("Transcribe audio"))
        transcribe.click().run(timeout=30)
        self.assertEqual(len(app.exception), 0, [error.message for error in app.exception])
        self.assertTrue(any("Record or upload an audio clip" in item.value for item in app.warning))


if __name__ == "__main__":
    unittest.main()
