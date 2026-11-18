const express = require('express');
const {
  createAcademicRecord,
  getAcademicRecordsForStudent,
  updateAcademicRecord,
} = require('../controllers/facultyAcademicController');
const { authMiddleware, requireRole } = require('../middleware/auth');

const router = express.Router();

router.use(authMiddleware, requireRole('faculty'));
router.post('/records', createAcademicRecord);
router.put('/records/:id', updateAcademicRecord);
router.get('/students/:studentId/records', getAcademicRecordsForStudent);

module.exports = router;