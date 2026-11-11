import unittest

from app import app, get_simple_response_text


class SimpleQATest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_returns_question_answer_for_any_input(self):
        answer = get_simple_response_text("what is ai")
        self.assertIn("AI", answer)
        self.assertNotIn("demo", answer.lower())

    def test_voice_process_returns_direct_answer_without_booking_prompt(self):
        response = self.client.post(
            "/process",
            data={"CallSid": "test-call", "SpeechResult": "what is ai"},
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("AI", body)
        self.assertNotIn("demo", body.lower())

    def test_voice_endpoint_returns_twili_xml(self):
        response = self.client.post(
            "/voice",
            data={"CallSid": "test-call", "From": "+15551234567"},
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("<Response>", body)
        self.assertIn("<Say>", body)


if __name__ == "__main__":
    unittest.main()
