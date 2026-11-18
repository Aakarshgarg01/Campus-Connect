const jwt = require('jsonwebtoken');
const mongoose = require('mongoose');
const User = require('../models/user');

async function authMiddleware(request, response, next) {
  const token = request.cookies?.campusconnect_token;

  if (!token) {
    return response.status(401).json({ message: 'Authentication required' });
  }

  let payload;
  try {
    if (!process.env.JWT_SECRET) {
      throw new Error('JWT_SECRET is not configured');
    }

    payload = jwt.verify(token, process.env.JWT_SECRET);
  } catch {
    return response.status(401).json({ message: 'Authentication required' });
  }

  if (!payload || typeof payload !== 'object' || typeof payload.userId !== 'string') {
    return response.status(401).json({ message: 'Authentication required' });
  }

  if (!mongoose.isValidObjectId(payload.userId)) {
    return response.status(401).json({ message: 'Authentication required' });
  }

  const user = await User.findById(payload.userId).select('_id role');
  if (!user || !['student', 'faculty'].includes(user.role)) {
    return response.status(401).json({ message: 'Authentication required' });
  }

  request.user = {
    id: user._id.toString(),
    role: user.role,
  };
  return next();
}

function requireRole(role) {
  if (!['student', 'faculty'].includes(role)) {
    throw new Error('Role must be student or faculty');
  }

  return (request, response, next) => {
    if (!request.user) {
      return response.status(401).json({ message: 'Authentication required' });
    }

    if (request.user.role !== role) {
      return response.status(403).json({ message: 'Access denied' });
    }

    return next();
  };
}

module.exports = { authMiddleware, requireRole };