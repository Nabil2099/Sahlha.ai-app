/// Base URL of the Sahlha FastAPI backend.
///
/// Override at run time with:
///   flutter run --dart-define API_BASE_URL=http://127.0.0.1:8000
///
/// Defaults:
/// - Android emulator -> http://10.0.2.2:8000
/// - Physical device over USB -> `adb reverse tcp:8000 tcp:8000`, then
///   run with --dart-define API_BASE_URL=http://127.0.0.1:8000
const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);
