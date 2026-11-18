const express = require('express');
const {
  generatePrediction,
  getPredictionHistory,
} = require('../controllers/predictionController');
const { authMiddleware, requireRole } = require('../middleware/auth');

const router = express.Router();

router.use(authMiddleware, requireRole('student'));
router.post('/generate', generatePrediction);
router.get('/', getPredictionHistory);

module.exports = router;