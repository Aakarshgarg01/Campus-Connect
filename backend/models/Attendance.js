const mongoose = require('mongoose');

const attendanceSchema = new mongoose.Schema({
  studentId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
  },
  semester: {
    type: Number,
    required: true,
    min: 1,
    validate: {
      validator: Number.isInteger,
      message: 'Semester must be a positive integer',
    },
  },
  attendancePercentage: {
    type: Number,
    required: true,
    min: 0,
    max: 100,
  },
}, { timestamps: true });

attendanceSchema.index(
  { studentId: 1, semester: 1 },
  { unique: true },
);

module.exports = mongoose.models.Attendance
  || mongoose.model('Attendance', attendanceSchema);