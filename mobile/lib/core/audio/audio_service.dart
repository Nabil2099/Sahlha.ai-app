import 'package:just_audio/just_audio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../api/api_client.dart';

part 'audio_service.g.dart';

/// Plays skill/lesson audio (Groq TTS WAVs). Authenticated via header.
/// Failures are reported as simple messages — learning never breaks.
class AudioService {
  AudioService(this._player, this._api);

  final AudioPlayer _player;
  final ApiClient _api;

  bool get playing => _player.playing;

  Stream<bool> get playingStream =>
      _player.playerStateStream.map((s) => s.playing);

  Future<String?> playUrl(String url) async {
    try {
      await _player.stop();
      // just_audio supports headers for the audio request.
      await _player.setUrl(url, headers: _authHeaders);
      await _player.play();
      return null;
    } catch (_) {
      return 'Audio is unavailable right now.';
    }
  }

  Future<void> stop() => _player.stop();

  Map<String, String> get _authHeaders {
    final token = _api.token;
    return {if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token'};
  }
}

@riverpod
AudioService audioService(AudioServiceRef ref) {
  final player = AudioPlayer();
  ref.onDispose(player.dispose);
  return AudioService(player, ref.watch(apiClientProvider));
}
