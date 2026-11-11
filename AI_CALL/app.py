from flask import Flask, request, render_template, jsonify, Response
from dotenv import load_dotenv
import os
from xml.sax.saxutils import escape

try:
    from twilio.twiml.voice_response import VoiceResponse, Gather
except ImportError:
    class VoiceResponse:
        def __init__(self):
            self.children = []

        def say(self, text, *args, **kwargs):
            self.children.append(("say", str(text), kwargs))

        def append(self, other):
            if hasattr(other, "to_xml"):
                self.children.append(("child", other, {}))

        def hangup(self):
            self.children.append(("hangup", None, {}))

        def to_xml(self):
            parts = []
            for kind, value, attrs in self.children:
                if kind == "say":
                    attrs_xml = "".join(
                        f' {name}="{escape(str(attr))}"'
                        for name, attr in attrs.items()
                        if attr is not None
                    )
                    parts.append(f"<Say{attrs_xml}>{escape(str(value))}</Say>")
                elif kind == "hangup":
                    parts.append("<Hangup/>")
                elif kind == "child":
                    parts.append(str(value))
            return f"<Response>{''.join(parts)}</Response>"

        def __str__(self):
            return self.to_xml()

    class Gather:
        def __init__(self, *args, **kwargs):
            self.children = []
            self.attrs = kwargs

        def say(self, text, *args, **kwargs):
            self.children.append(("say", str(text), kwargs))

        def to_xml(self):
            attrs_xml = "".join(
                f' {name}="{escape(str(attr))}"'
                for name, attr in self.attrs.items()
                if attr is not None
            )
            parts = []
            for kind, value, attrs in self.children:
                if kind == "say":
                    say_attrs_xml = "".join(
                        f' {name}="{escape(str(attr))}"'
                        for name, attr in attrs.items()
                        if attr is not None
                    )
                    parts.append(f"<Say{say_attrs_xml}>{escape(str(value))}</Say>")
            return f"<Gather{attrs_xml}>{''.join(parts)}</Gather>"

        def __str__(self):
            return self.to_xml()

# Import our custom systems
from knowledge_base import COURSE_INFO, FAQS
from question_answerer import detect_question_type, generate_answer
from sales_intelligence import (
    get_intro_message, get_interest_check, get_yes_response, get_no_response,
    get_answer_intro, get_after_answer, get_demo_message, get_close, handle_objection
)

app = Flask(__name__)
load_dotenv()

print("=" * 70)
print("🔥 ADVANCED AI Q&A CALL AGENT")
print("✅ Answers general questions during calls")
print("✅ No booking/slot management — pure Q&A")
print("=" * 70)

# =============================
# CALL STATE TRACKING
# =============================
call_state = {}
conversation_history = {}
turn_count = {}
student_interest = {}
student_phone = {}

def get_state(call_id):
    return call_state.get(call_id, {
        "stage": "intro",
        "questions_asked": 0,
        "demo_offered": False,
        "course_selected": None,
        "demo_date": None,
        "demo_time": None,
        "student_name": None,
        "student_mobile": None
    })

def update_state(call_id, state):
    call_state[call_id] = state


def is_affirmative(text):
    text_lower = text.lower()
    return any(word in text_lower for word in ["yes", "ya", "yup", "sure", "okay", "of course", "absolutely", "want", "i do", "నేను", "అవును", "సరే"])


def is_negative(text):
    text_lower = text.lower()
    return any(word in text_lower for word in ["no", "don't", "dont", "nah", "not interested", "కాదు", "లేదు"])


def add_to_history(call_id, role, text):
    if call_id not in conversation_history:
        conversation_history[call_id] = []
    conversation_history[call_id].append({"role": role, "text": text})


def get_turn(call_id):
    return turn_count.get(call_id, 0)


def increment_turn(call_id):
    turn_count[call_id] = get_turn(call_id) + 1


def get_stage_followup_prompt(state):
    return "Ask me anything else. I can answer about courses, fees, placements, projects, AI, and more."


def get_simple_response_text(user_input):
    question_type, direct_answer = detect_question_type(user_input)
    if direct_answer:
        return direct_answer

    if question_type == "unclear":
        return generate_answer(question_type, user_input)

    answer = generate_answer(question_type, user_input)
    if question_type not in ["who_are_you", "what_can_you_do"]:
        return get_answer_intro(question_type) + " " + answer
    return answer


def build_twilio_error_response(message=None):
    response = VoiceResponse()
    response.say(
        message or "Sorry, the system encountered an error. Please try again later.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    response.hangup()
    return Response(str(response), mimetype="application/xml")


def try_general_question_response(response, call_id, user_input, state):
    ai_response = get_simple_response_text(user_input)
    response.say(ai_response, voice="Polly.Aditi", language="en-IN")
    add_to_history(call_id, "Agent", ai_response)

    gather = Gather(
        input="speech",
        action="/process",
        method="POST",
        timeout=10,
        speechTimeout="auto",
        language="en-IN"
    )
    follow_up = "Ask me anything else. I can answer about courses, fees, placements, projects, AI, and more."
    gather.say(follow_up, voice="Polly.Aditi", language="en-IN")
    response.append(gather)
    return True

# =============================
# HEALTH CHECK
# =============================
@app.route("/", methods=["GET"])
def health():
    return "✅ Real AI Sales Agent is running with ACTUAL course knowledge!"


# =============================
# SIMPLE WEB DASHBOARD
# =============================
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("index.html")


@app.route("/trigger_call", methods=["POST"])
def trigger_call():
    """Trigger an outbound call via Twilio (uses same env vars as call.py).
    Expects JSON: { "phone": "+123..." }
    """
    from twilio.rest import Client
    phone = request.json.get("phone") if request.is_json else request.form.get("phone")
    if not phone:
        return jsonify({"error": "Phone number required"}), 400

    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    VOICE_WEBHOOK_URL = os.getenv("VOICE_WEBHOOK_URL", "").strip()
    SIMULATE_MODE = os.getenv("SIMULATE_MODE", "").strip().lower() in ("1", "true", "yes")

    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, VOICE_WEBHOOK_URL]):
        return jsonify({"error": "Missing Twilio configuration in environment"}), 500

    if SIMULATE_MODE or os.getenv("SIMULATE_MODE", "").lower() in ("1", "true", "yes"):
        # Simulate invocation of the webhook similar to call.py
        import urllib.parse, urllib.request
        form_data = urllib.parse.urlencode({
            "CallSid": "SIMULATED_CALL_SID",
            "From": phone,
            "To": TWILIO_FROM_NUMBER,
            "CallStatus": "in-progress",
        }).encode("utf-8")
        req = urllib.request.Request(VOICE_WEBHOOK_URL, data=form_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
            return jsonify({"status": "simulated", "webhook_response": body})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    # Real call via Twilio
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        call = client.calls.create(to=phone, from_=TWILIO_FROM_NUMBER, url=VOICE_WEBHOOK_URL)
        return jsonify({"status": "started", "call_sid": call.sid})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# =============================
# INITIAL VOICE CALL ENDPOINT
# =============================
@app.route("/voice", methods=["POST"])
def voice():
    """
    When student receives the call, this is what they hear first.
    The system now answers questions directly instead of running a booking flow.
    """
    try:
        call_id = request.form.get("CallSid", "default")
        phone = request.form.get("From", "unknown")

        student_phone[call_id] = phone
        call_state[call_id] = {
            "stage": "intro",
            "questions_asked": 0,
            "demo_offered": False,
            "course_selected": None,
            "demo_date": None,
            "demo_time": None,
            "student_name": None,
            "student_mobile": None
        }

        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action="/process",
            method="POST",
            timeout=10,
            speechTimeout="auto",
            language="en-IN"
        )

        intro_message = "Hello! I can answer your questions directly. Ask me anything about the course, fees, placements, projects, AI, or technology."
        gather.say(intro_message, voice="Polly.Aditi", language="en-IN")
        response.append(gather)

        return Response(str(response), mimetype="application/xml")
    except Exception as exc:
        print(f"Error in /voice: {exc}", exc_info=True)
        return build_twilio_error_response()

# =============================
# MAIN PROCESSING ENDPOINT
# =============================
@app.route("/process", methods=["POST"])
def process():
    """
    MAIN ENGINE: Listens to student, detects question, gives REAL answer
    """
    try:
        user_input = request.form.get("SpeechResult", "").strip()
        call_id = request.form.get("CallSid", "default")
        
        response = VoiceResponse()
        state = get_state(call_id)
        current_turn = get_turn(call_id)

        gather = Gather(
            input="speech",
            action="/process",
            method="POST",
            timeout=10,
            speechTimeout="auto",
            language="en-IN"
        )
        
        # =============================
        # HANDLE NO SPEECH
        # =============================
        if not user_input:
            response.say(
                "Sorry, I could not hear you clearly. Please repeat. Ask about course, fees, placements, or anything else.",
                voice="Polly.Aditi",
                language="en-IN"
            )
            response.append(gather)
            return str(response)
        
        # =============================
        # HANDLE HARD EXIT
        # =============================
        if any(word in user_input.lower() for word in ["stop calling", "don't call", "remove me", "not interested at all"]):
            response.say("Okay, no problem! All the best!", voice="Polly.Aditi", language="en-IN")
            response.hangup()
            return str(response)
        
        # =============================
        # TRACK THE CONVERSATION
        # =============================
        add_to_history(call_id, "Student", user_input)
        increment_turn(call_id)
        current_turn = get_turn(call_id)
        
        print(f"\n[Turn {current_turn}] Student: {user_input}")

        ai_response = get_simple_response_text(user_input)
        response.say(ai_response, voice="Polly.Aditi", language="en-IN")
        add_to_history(call_id, "Agent", ai_response)

        follow_up = get_stage_followup_prompt(get_state(call_id))
        gather.say(follow_up, voice="Polly.Aditi", language="en-IN")
        response.append(gather)
        return Response(str(response), mimetype="application/xml")
    except Exception as exc:
        print(f"Error in /process: {exc}", exc_info=True)
        return build_twilio_error_response()

# =============================
# RUN THE APP
# =============================
if __name__ == "__main__":
    print("\n🚀 Starting AI Q&A Call Agent...")
    print("📱 Webhook endpoint: POST /voice")
    print("✅ Responds to spoken questions during calls")
    print("✅ Uses the local knowledge base to answer\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
