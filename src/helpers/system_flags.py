phone_call_active = False

def set_phone_call_active(value: bool):
    global phone_call_active
    phone_call_active = value

def get_phone_call_active() -> bool:
    return phone_call_active