const express = require('express');
const {
  getImprovementZone,
  getPerformance,
  getProfile,
  getTarget,
  updateTarget,
} = require('../controllers/studentController');
const { authMiddleware, requireRole } = require('../middleware/auth');

const router = express.Router();

router.use(authMiddleware, requireRole('student'));
router.get('/profile', getProfile);
router.get('/performance', getPerformance);
router.get('/target', getTarget);
router.put('/target', updateTarget);
router.get('/improvement-zone', getImprovementZone);

module.exports = router;