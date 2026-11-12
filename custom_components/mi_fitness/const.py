"""Constants for Mi Fitness integration."""

DOMAIN = "mi_fitness"

CONF_USER_ID       = "user_id"
CONF_C_USER_ID     = "c_user_id"
CONF_SSECURITY     = "ssecurity"
CONF_SERVICE_TOKEN = "service_token"
CONF_REGION        = "region"
CONF_PHONE_ID      = "phone_id"

# Path B — auto login
CONF_USERNAME      = "username"
CONF_PASSWORD      = "password"
CONF_AUTH_METHOD   = "auth_method"
CONF_PASS_TOKEN    = "pass_token"    # passToken — used for silent serviceToken refresh
# Persisted login deviceId cookie (an_<32 hex>). Must stay STABLE across logins and
# silent refreshes so Xiaomi remembers the device after one trusted 2FA (trust=true).
# NOTE: unrelated to CONF_PHONE_ID above, which is a data-API query parameter.
CONF_LOGIN_DEVICE_ID = "login_device_id"

AUTH_METHOD_TOKENS   = "tokens"    # Path A: manual token entry
AUTH_METHOD_PASSWORD = "password"  # Path B: username + password auto-login

REGIONS = ["us", "de", "sg", "cn", "ru", "i2"]
DEFAULT_REGION = "de"

SCAN_INTERVAL_MINUTES = 15

# Time windows read on every poll. The cloud is queried by range
# (get_fitness_data_by_time), not by an incremental watermark.
INITIAL_WINDOW_DAYS = 14   # first poll after a start/reload
REFRESH_WINDOW_DAYS = 3    # every later poll (overlap absorbs late syncs)

STORAGE_KEY = "mi_fitness_state"
STORAGE_VERSION = 2

# Sensor keys in the API response
KEY_STEPS              = "steps"
KEY_HEART_RATE         = "heart_rate"
KEY_RESTING_HEART_RATE = "resting_heart_rate"
KEY_SLEEP              = "sleep"
KEY_CALORIES           = "calories"
KEY_WEIGHT             = "weight"
KEY_VITALITY           = "vitality"
KEY_VALID_STAND        = "valid_stand"
KEY_SPO2               = "spo2"
KEY_STRESS             = "stress"

# Metrics requested for every window. Keys an account does not produce
# (for example sleep or weight without the matching device) simply return
# an empty page and are ignored.
LIVE_DATA_KEYS = (
    KEY_STEPS,
    KEY_CALORIES,
    KEY_HEART_RATE,
    KEY_RESTING_HEART_RATE,
    KEY_SPO2,
    KEY_STRESS,
    KEY_VALID_STAND,
    KEY_VITALITY,
    KEY_WEIGHT,
)

# Device info
DEVICE_MANUFACTURER = "Xiaomi"
DEVICE_MODEL        = "Mi Fitness Account"
