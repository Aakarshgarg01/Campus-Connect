const mongoose = require('mongoose');
const Prediction = require('../models/Prediction');
const predictionService = require('../services/predictionService');

async function generatePrediction(request, response) {
  const body = request.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return response.status(400).json({ message: 'A semester and prediction stage are required.' });
  }

  if (Object.keys(body).some((key) => !['semester', 'stage'].includes(key))) {
    return response.status(400).json({ message: 'Only semester and stage may be provided.' });
  }

  const { semester, stage } = body;
  if (!Number.isInteger(semester) || semester < 1) {
    return response.status(400).json({ message: 'Semester must be a positive integer.' });
  }

  if (!['stage1', 'stage2'].includes(stage)) {
    return response.status(400).json({ message: 'Stage must be stage1 or stage2.' });
  }

  const authenticatedUserId = request.user?.userId || request.user?.id;
  if (!mongoose.isObjectIdOrHexString(authenticatedUserId)) {
    return response.status(401).json({ message: 'Authentication required' });
  }

  const result = await predictionService.generatePrediction(authenticatedUserId, semester, stage);
  const savedPrediction = await Prediction.create({
    studentId: authenticatedUserId,
    semester,
    stage: result.stage,
    predictedFinalPerformance: result.predictedFinalPerformance,
  });

  return response.status(201).json({
    message: 'Prediction generated successfully',
    prediction: {
      id: savedPrediction._id.toString(),
      semester: savedPrediction.semester,
      stage: savedPrediction.stage,
      predictedFinalPerformance: savedPrediction.predictedFinalPerformance,
      createdAt: savedPrediction.createdAt,
    },
  });
}

async function getPredictionHistory(request, response) {
  const filter = {
    studentId: request.user?.userId || request.user?.id,
  };

  if (request.query.semester !== undefined) {
    const semesterText = request.query.semester;
    const semester = Number(semesterText);
    if (typeof semesterText !== 'string' || !Number.isInteger(semester) || semester < 1) {
      return response.status(400).json({ message: 'Semester must be a positive integer.' });
    }
    filter.semester = semester;
  }

  const predictions = await Prediction.find(filter)
    .select('semester stage predictedFinalPerformance createdAt')
    .sort({ createdAt: -1, _id: -1 })
    .lean();

  return response.status(200).json({
    predictions: predictions.map((prediction) => ({
      id: prediction._id.toString(),
      semester: prediction.semester,
      stage: prediction.stage,
      predictedFinalPerformance: prediction.predictedFinalPerformance,
      createdAt: prediction.createdAt,
    })),
  });
}

module.exports = { generatePrediction, getPredictionHistory };