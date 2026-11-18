const mongoose = require('mongoose');

const predictionSchema = new mongoose.Schema({
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
  stage: {
    type: String,
    required: true,
    enum: ['stage1', 'stage2'],
  },
  predictedFinalPerformance: {
    type: Number,
    required: true,
    min: 0,
    max: 100,
  },
}, {
  timestamps: {
    createdAt: true,
    updatedAt: false,
  },
});

predictionSchema.index({ studentId: 1, semester: 1, createdAt: 1 });

module.exports = mongoose.models.Prediction
  || mongoose.model('Prediction', predictionSchema);