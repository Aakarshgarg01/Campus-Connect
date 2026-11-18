const mongoose = require('mongoose');

const userSchema = new mongoose.Schema({
  name: {
    type: String,
    required: true,
    trim: true,
  },
  email: {
    type: String,
    required: true,
    unique: true,
    lowercase: true,
    trim: true,
  },
  passwordHash: {
    type: String,
    required: true,
    select: false,
  },
  role: {
    type: String,
    required: true,
    enum: ['student', 'faculty'],
  },
  rollNumber: {
    type: String,
    trim: true,
    uppercase: true,
    required() {
      return this.role === 'student';
    },
    unique: true,
    sparse: true,
  },
  employeeId: {
    type: String,
    trim: true,
    uppercase: true,
    required() {
      return this.role === 'faculty';
    },
    unique: true,
    sparse: true,
  },
  department: {
    type: String,
    trim: true,
  },
  semester: {
    type: Number,
    min: 1,
    required() {
      return this.role === 'student';
    },
  },
}, {
  timestamps: true,
});

module.exports = mongoose.models.User || mongoose.model('User', userSchema);