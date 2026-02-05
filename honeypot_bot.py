import time
import random

# ================= HUMAN-LIKE TYPING =================
def human_typing_delay(text):
    time.sleep(min(len(text) * 0.02, 1.5))


# ================= CONFIDENCE SCORE =================
def compute_confidence(step, detected_keywords):
    return min(len(detected_keywords) * 15 + step * 5, 100)


# ================= HACKATHON-SAFE HONEYPOT =================
def honeypot_reply(
    message,
    detected_keywords,
    step,
    model_name=None,
    provider=None
):
    confidence = compute_confidence(step, detected_keywords)

    replies = [
        "I am not fully understanding. Can you explain once more?",
        "This sounds interesting. What should I do next?",
        "Are you sure this is safe? I am a bit confused.",
        "Do I need to pay anything for this?",
        "Why is this so urgent? Please explain clearly."
    ]

    reply = replies[step % len(replies)]
    human_typing_delay(reply)
    return reply
