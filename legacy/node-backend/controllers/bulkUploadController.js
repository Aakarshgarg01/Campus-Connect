const { previewBulkAcademicUpload, confirmBulkAcademicUpload } = require('../services/bulkUploadService');

async function previewBulkUpload(request, response) {
  try {
    if (!request.file) {
      return response.status(400).json({
        valid: false,
        summary: { totalRows: 0, validRows: 0, errorRows: 0 },
        errors: [{ row: null, field: 'file', message: 'A file is required.' }],
        preview: [],
      });
    }

    const requestSemester = request.body && request.body.semester !== undefined ? request.body.semester : undefined;
    const result = await previewBulkAcademicUpload(request.file, requestSemester);
    if (!result.valid) {
      return response.status(400).json({
        valid: false,
        summary: result.summary,
        errors: result.errors,
        preview: [],
      });
    }

    return response.status(200).json({
      valid: true,
      uploadId: result.uploadId,
      summary: result.summary,
      errors: [],
      preview: result.preview,
    });
  } catch (error) {
    return response.status(400).json({
      valid: false,
      summary: { totalRows: 0, validRows: 0, errorRows: 0 },
      errors: [{ row: null, field: 'file', message: error.message || 'Unable to process file.' }],
      preview: [],
    });
  }
}

async function confirmBulkUpload(request, response) {
  try {
    const { uploadId } = request.body || {};
    if (!uploadId || typeof uploadId !== 'string') {
      return response.status(400).json({ message: 'A valid uploadId is required.' });
    }

    const result = await confirmBulkAcademicUpload(uploadId);
    return response.status(200).json(result);
  } catch (error) {
    return response.status(400).json({ message: error.message || 'Bulk upload confirmation failed.' });
  }
}

module.exports = {
  previewBulkUpload,
  confirmBulkUpload,
};
