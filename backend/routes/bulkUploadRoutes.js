const express = require('express');
const multer = require('multer');
const { authMiddleware, requireRole } = require('../middleware/auth');
const { previewBulkUpload, confirmBulkUpload } = require('../controllers/bulkUploadController');

const router = express.Router();
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 5 * 1024 * 1024,
  },
  fileFilter: (_request, file, callback) => {
    const allowedExtensions = ['.csv', '.xls', '.xlsx'];
    const extension = file.originalname.split('.').pop()?.toLowerCase();
    const isAllowed = extension && allowedExtensions.includes(`.${extension}`);
    if (!isAllowed) {
      return callback(new Error('Unsupported file type. Upload a CSV, XLS, or XLSX file.'));
    }

    return callback(null, true);
  },
});

router.use(authMiddleware, requireRole('faculty'));
router.post('/preview', upload.single('file'), previewBulkUpload);
router.post('/confirm', confirmBulkUpload);
router.use((error, _request, response, next) => {
  if (error instanceof multer.MulterError || error.message?.startsWith('Unsupported file type')) {
    return response.status(400).json({
      valid: false,
      summary: { totalRows: 0, validRows: 0, errorRows: 0 },
      errors: [{ row: null, field: 'file', message: error.message }],
      preview: [],
    });
  }

  return next(error);
});

module.exports = router;

