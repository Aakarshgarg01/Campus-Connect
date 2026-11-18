const express = require('express');
const { currentUser, login, logout } = require('../controllers/auth-controller');
const { authMiddleware } = require('../middleware/auth');

const router = express.Router();

router.post('/login', login);
router.post('/logout', logout);
router.get('/me', authMiddleware, currentUser);

module.exports = router;