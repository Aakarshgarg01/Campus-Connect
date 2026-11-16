const mongoose = require('mongoose');

const monitoringSchema = new mongoose.Schema({
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
  status: {
    type: String,
    enum: ['Not Contacted', 'Contacted', 'Counselling Done', 'Under Monitoring', 'Improved'],
    default: 'Not Contacted',
  },
  notes: {
    type: String,
    trim: true,
  },
  updatedBy: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
  },
}, { timestamps: true });

monitoringSchema.index(
  { studentId: 1, semester: 1 },
  { unique: true },
);

module.exports = mongoose.models.Monitoring
  || mongoose.model('Monitoring', monitoringSchema);