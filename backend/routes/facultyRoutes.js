const express = require('express');
const { authMiddleware, requireRole } = require('../middleware/auth');
const {
  getFacultyStudents,
  getFacultyStudentDetail,
  getFacultyBenchmark,
  updateFacultyBenchmark,
  getMonitoringList,
  updateMonitoring,
} = require('../controllers/facultyController');

const router = express.Router();

router.use(authMiddleware, requireRole('faculty'));

router.get('/students', getFacultyStudents);
router.get('/students/:studentId', getFacultyStudentDetail);
router.get('/benchmark', getFacultyBenchmark);
router.put('/benchmark', updateFacultyBenchmark);
router.get('/monitoring', getMonitoringList);
router.put('/monitoring/:studentId', updateMonitoring);

module.exports = router;
