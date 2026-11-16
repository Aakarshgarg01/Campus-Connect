const mongoose = require('mongoose');

const facultyBenchmarkSchema = new mongoose.Schema({
  semester: {
    type: Number,
    required: true,
    min: 1,
    validate: {
      validator: Number.isInteger,
      message: 'Semester must be a positive integer',
    },
  },
  department: {
    type: String,
    required: true,
    trim: true,
  },
  benchmarkPerformance: {
    type: Number,
    required: true,
    min: 0,
    max: 100,
  },
  createdBy: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
  },
}, { timestamps: true });

facultyBenchmarkSchema.index(
  { semester: 1, department: 1 },
  { unique: true },
);

module.exports = mongoose.models.FacultyBenchmark
  || mongoose.model('FacultyBenchmark', facultyBenchmarkSchema);