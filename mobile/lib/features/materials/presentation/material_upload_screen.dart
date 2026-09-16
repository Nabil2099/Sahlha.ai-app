import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/sahlha_colors.dart';
import '../../../core/theme/sahlha_spacing.dart';
import '../../../core/widgets/sahlha_widgets.dart';
import 'upload_controller.dart';

/// Teacher: upload official classroom material (PDF, DOCX, PPTX, TXT, images).
class MaterialUploadScreen extends ConsumerStatefulWidget {
  const MaterialUploadScreen({super.key, this.classroomId});

  final String? classroomId;

  @override
  ConsumerState<MaterialUploadScreen> createState() =>
      _MaterialUploadScreenState();
}

class _MaterialUploadScreenState extends ConsumerState<MaterialUploadScreen> {
  final _title = TextEditingController();

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) ref.read(uploadControllerProvider.notifier).reset();
    });
  }

  @override
  void dispose() {
    _title.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final state = ref.watch(uploadControllerProvider);
    final controller = ref.read(uploadControllerProvider.notifier);

    ref.listen(uploadControllerProvider, (prev, next) {
      if (prev?.material == null && next.material != null) {
        final roomId = next.material!.classroomId ?? widget.classroomId;
        final location = Uri(
          path: '/teacher/materials/${next.material!.id}',
          queryParameters: roomId == null ? null : {'classroomId': roomId},
        ).toString();
        context.pushReplacement(location);
      }
      if (next.error != null && next.error != prev?.error) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(next.error!)));
      }
    });

    return Scaffold(
      appBar: const SahlhaAppBar(title: 'Upload Material'),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(SahlhaSpacing.page),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Upload learning material', style: text.headlineSmall),
              const SizedBox(height: SahlhaSpacing.sm),
              Text(
                'PDF, DOCX, PPTX, TXT or images (max 25 MB). Official classroom curriculum — students see it after you approve the practice.',
                style: text.bodyMedium?.copyWith(color: SahlhaColors.muted),
              ),
              const SizedBox(height: SahlhaSpacing.xl),
              InkWell(
                onTap: state.picking || state.uploading || state.extracting
                    ? null
                    : controller.pickFile,
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  padding: const EdgeInsets.all(SahlhaSpacing.xl),
                  decoration: BoxDecoration(
                    color: SahlhaColors.tealFaint,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: SahlhaColors.tealSoft,
                      width: 1.5,
                    ),
                  ),
                  child: Column(
                    children: [
                      Container(
                        width: 64,
                        height: 64,
                        decoration: const BoxDecoration(
                          color: SahlhaColors.teal,
                          shape: BoxShape.circle,
                        ),
                        child: state.picking
                            ? const Padding(
                                padding: EdgeInsets.all(18),
                                child: CircularProgressIndicator(
                                  color: Colors.white,
                                  strokeWidth: 2.5,
                                ),
                              )
                            : const Icon(
                                Icons.add,
                                color: Colors.white,
                                size: 32,
                              ),
                      ),
                      const SizedBox(height: SahlhaSpacing.md),
                      Text(
                        state.fileName ?? 'Choose file',
                        style: text.titleMedium,
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: SahlhaSpacing.lg),
              TextField(
                controller: _title,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(
                  labelText: 'Title (optional)',
                  hintText: 'e.g. Fractions — Chapter 3',
                ),
              ),
              const SizedBox(height: SahlhaSpacing.xl),
              SahlhaPrimaryButton(
                label: state.uploading ? 'Uploading…' : 'Upload and process',
                loading: state.uploading,
                onPressed:
                    state.picking ||
                        (state.filePath == null && state.fileBytes == null) ||
                        widget.classroomId == null
                    ? null
                    : () => controller.upload(
                        title: _title.text.trim(),
                        classroomId: widget.classroomId,
                      ),
              ),
              const SizedBox(height: SahlhaSpacing.sm),
              Text(
                'Sahlha will read the document. On the next screen, find learning skills and generate practice questions for your review.',
                style: text.bodySmall?.copyWith(color: SahlhaColors.muted),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
