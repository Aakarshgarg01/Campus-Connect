const mongoose = require('mongoose');

const assessmentSchema = new mongoose.Schema({
  obtained: {
    type: Number,
    required: true,
    min: 0,
    validate: {
      validator(value) {
        return value <= this.maximum;
      },
      message: 'Obtained marks cannot exceed maximum marks',
    },
  },
  maximum: {
    type: Number,
    required: true,
    min: [Number.MIN_VALUE, 'Maximum marks must be greater than 0'],
  },
}, { _id: false });

const academicRecordSchema = new mongoose.Schema({
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
  subjectName: {
    type: String,
    required: true,
    trim: true,
  },
  internal1: {
    type: assessmentSchema,
    default: undefined,
  },
  internal2: {
    type: assessmentSchema,
    default: undefined,
  },
  assignment: {
    type: assessmentSchema,
    default: undefined,
  },
}, { timestamps: true });

academicRecordSchema.index(
  { studentId: 1, semester: 1, subjectName: 1 },
  { unique: true },
);

module.exports = mongoose.models.AcademicRecord
  || mongoose.model('AcademicRecord', academicRecordSchema);