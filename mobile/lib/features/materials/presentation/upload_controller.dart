import 'package:file_picker/file_picker.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/api/api_exception.dart';
import '../data/material_repository.dart';
import '../domain/material.dart';

part 'upload_controller.freezed.dart';
part 'upload_controller.g.dart';

@freezed
class UploadState with _$UploadState {
  const factory UploadState({
    @Default(false) bool picking,
    String? fileName,
    String? filePath,
    @Default(false) bool uploading,
    Material? material,
    String? error,
    @Default(false) bool extracting,
    @Default(false) bool generating,
    @Default('') String step,
  }) = _UploadState;
}

@riverpod
class UploadController extends _$UploadController {
  @override
  UploadState build() => const UploadState();

  Future<void> pickFile() async {
    state = state.copyWith(picking: true, error: null);
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: [
          'pdf',
          'docx',
          'pptx',
          'txt',
          'md',
          'png',
          'jpg',
          'jpeg'
        ],
        withData: false,
      );
      final file = result?.files.single;
      if (file == null || file.path == null) {
        state = state.copyWith(picking: false);
        return;
      }
      state = state.copyWith(
          picking: false, fileName: file.name, filePath: file.path);
    } catch (_) {
      state = state.copyWith(
          picking: false, error: 'Could not open the file picker.');
    }
  }

  Future<void> upload(
      {String title = '', String? classroomId, String? childStudentId}) async {
    final path = state.filePath;
    final name = state.fileName;
    if (path == null || name == null) {
      state = state.copyWith(error: 'Choose a file first.');
      return;
    }
    state = state.copyWith(uploading: true, error: null, step: 'Uploading…');
    try {
      final material = await ref.read(materialRepositoryProvider).upload(
            filePath: path,
            fileName: name,
            title: title.isEmpty ? name : title,
            classroomId: classroomId,
            childStudentId: childStudentId,
          );
      state = state.copyWith(uploading: false, material: material, step: '');
      ref.invalidate(materialListProvider);
    } on ApiException catch (e) {
      state = state.copyWith(uploading: false, error: e.message, step: '');
    }
  }

  Future<void> extractSkills(String materialId) async {
    state = state.copyWith(
        extracting: true, error: null, step: 'Finding learning skills…');
    try {
      await ref.read(materialRepositoryProvider).extractSkills(materialId);
      final material = await ref.read(materialRepositoryProvider).get(materialId);
      state = state.copyWith(extracting: false, material: material, step: '');
      ref.invalidate(materialSkillsProvider);
      ref.invalidate(materialListProvider);
    } on ApiException catch (e) {
      state = state.copyWith(extracting: false, error: e.message, step: '');
    }
  }

  Future<void> generateBanks(String materialId) async {
    state =
        state.copyWith(generating: true, error: null, step: 'Generating practice…');
    try {
      await ref.read(materialRepositoryProvider).generateBanks(materialId);
      final material = await ref.read(materialRepositoryProvider).get(materialId);
      state = state.copyWith(generating: false, material: material, step: '');
      ref.invalidate(materialListProvider);
    } on ApiException catch (e) {
      state = state.copyWith(generating: false, error: e.message, step: '');
    }
  }

  void reset() => state = const UploadState();
}
