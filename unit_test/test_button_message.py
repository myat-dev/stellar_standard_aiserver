import unittest

from message_templates.line_push_template import (
    CallButtonMessage,
    CheckAvailablityMessage,
)

USER_ID = "U0452392b0ec0454c327931b2272571e0"
NAME = "前田"
PHONE_NUMBER = "090-1123-2123"


class TestCallButtonMessage(unittest.TestCase):

    @unittest.skip("This test check button message payload.")
    def test_call_button_message_payload(self):
        message = CallButtonMessage(USER_ID, NAME, PHONE_NUMBER)
        expected_payload = {
            "to": USER_ID,
            "messages": [
                {
                    "type": "template",
                    "altText": f"{NAME}がお寺に訪問しました。連絡先は{PHONE_NUMBER}です。\n 今すぐお電話をかけますか？",
                    "template": {
                        "type": "buttons",
                        "text": f"{NAME}がお寺に訪問しました。連絡先は{PHONE_NUMBER}です。\n 今すぐお電話をかけますか？",
                        "actions": [
                            {
                                "type": "uri",
                                "label": "お電話をかける",
                                "uri": f"tel:{PHONE_NUMBER.replace('-', '')}",
                            }
                        ],
                    },
                }
            ],
        }
        self.assertEqual(message.create_payload(), expected_payload)

    @unittest.skip("This test actually sends a message to the LINE API.")
    def test_call_button_message_send_real(self):
        """This test actually sends a message to the LINE API."""
        message = CallButtonMessage(USER_ID, NAME, PHONE_NUMBER)
        response = (
            message.send()
        )  # Assuming this method sends the request using requests.post()

        # Check if the request was successful
        self.assertEqual(response.status_code, 200)
        print("Message sent successfully!")

    def test_check_availability_message(self):
        message = CheckAvailablityMessage(USER_ID)
        response = message.send()

        # Check if the request was successful
        self.assertEqual(response.status_code, 200)
        print("Message sent successfully!")


if __name__ == "__main__":
    unittest.main()
