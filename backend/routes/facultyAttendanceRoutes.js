const express = require('express');
const { createOrUpdateAttendance } = require('../controllers/facultyAttendanceController');
const { authMiddleware, requireRole } = require('../middleware/auth');

const router = express.Router();

router.use(authMiddleware, requireRole('faculty'));
router.put('/', createOrUpdateAttendance);

module.exports = router;