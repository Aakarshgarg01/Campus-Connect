const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const User = require('../models/user');
const toSafeUser = require('../utils/safe-user');

function getCookieOptions() {
  const isProduction = process.env.NODE_ENV === 'production';
  return {
    httpOnly: true,
    secure: isProduction,
    sameSite: isProduction ? 'none' : 'lax',
    path: '/',
  };
}

async function login(request, response) {
  const { identifier, password } = request.body || {};
  if (typeof identifier !== 'string' || typeof password !== 'string' || !identifier.trim()) {
    return response.status(401).json({ message: 'Invalid credentials' });
  }

  const normalizedIdentifier = identifier.trim();
  const user = await User.findOne({
    $or: [
      { email: normalizedIdentifier.toLowerCase() },
      { rollNumber: normalizedIdentifier.toUpperCase() },
      { employeeId: normalizedIdentifier.toUpperCase() },
    ],
  }).select('+passwordHash');

  if (!user || !(await bcrypt.compare(password, user.passwordHash))) {
    return response.status(401).json({ message: 'Invalid credentials' });
  }

  if (!process.env.JWT_SECRET) {
    throw new Error('JWT_SECRET is required for authentication');
  }

  const token = jwt.sign(
    { userId: user._id.toString(), role: user.role },
    process.env.JWT_SECRET,
    { expiresIn: process.env.JWT_EXPIRES_IN || '1d' },
  );

  response.cookie('campusconnect_token', token, getCookieOptions());
  return response.status(200).json({
    message: 'Login successful',
    user: toSafeUser(user),
  });
}

function logout(request, response) {
  response.clearCookie('campusconnect_token', getCookieOptions());
  return response.status(200).json({ message: 'Logout successful' });
}

async function currentUser(request, response) {
  const user = await User.findById(request.user.id);
  if (!user) {
    return response.status(401).json({ message: 'Authentication required' });
  }

  return response.status(200).json({ user: toSafeUser(user) });
}

module.exports = { login, logout, currentUser };