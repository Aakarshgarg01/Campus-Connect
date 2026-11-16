const axios = require('axios');
const AcademicRecord = require('../models/AcademicRecord');
const Attendance = require('../models/Attendance');

const STAGE_REQUIREMENTS = {
  stage1: ['internal1', 'assignment'],
  stage2: ['internal1', 'internal2', 'assignment'],
};

function createServiceError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function normalizeAssessment(assessment) {
  if (!assessment
    || typeof assessment.obtained !== 'number'
    || typeof assessment.maximum !== 'number'
    || assessment.maximum <= 0
    || assessment.obtained < 0
    || assessment.obtained > assessment.maximum) {
    return null;
  }

  return (assessment.obtained / assessment.maximum) * 100;
}

function averageAssessment(records, field) {
  const percentages = records.map((record) => normalizeAssessment(record[field]));
  if (percentages.length === 0 || percentages.some((percentage) => percentage === null)) {
    return null;
  }

  return percentages.reduce((total, percentage) => total + percentage, 0) / percentages.length;
}

function roundPercentage(value) {
  return Number(value.toFixed(2));
}

function getMlServiceUrl() {
  const serviceUrl = process.env.ML_SERVICE_URL;
  if (!serviceUrl) {
    throw createServiceError(503, 'ML prediction service is currently unavailable.');
  }
  return serviceUrl.replace(/\/+$/, '');
}

function validateMlResponse(data, stage) {
  const prediction = data?.predicted_final_performance;
  if (data?.stage !== stage
    || typeof prediction !== 'number'
    || !Number.isFinite(prediction)
    || prediction < 0
    || prediction > 100) {
    throw createServiceError(502, 'ML prediction service returned an invalid response.');
  }

  return roundPercentage(prediction);
}

async function postToMlService(path, payload, stage) {
  let response;
  try {
    response = await axios.post(`${getMlServiceUrl()}${path}`, payload, { timeout: 10000 });
  } catch (error) {
    if (!axios.isAxiosError(error) && error.status) {
      throw error;
    }

    if (axios.isAxiosError(error) && error.response && error.response.status < 500) {
      throw createServiceError(400, 'ML prediction service rejected the prediction input.');
    }

    throw createServiceError(503, 'ML prediction service is currently unavailable.');
  }

  return {
    stage,
    predictedFinalPerformance: validateMlResponse(response.data, stage),
  };
}

async function buildPredictionInputs(studentId, semester, stage) {
  const [records, attendance] = await Promise.all([
    AcademicRecord.find({ studentId, semester })
      .select('internal1 internal2 assignment')
      .lean(),
    Attendance.findOne({ studentId, semester })
      .select('attendancePercentage')
      .lean(),
  ]);

  if (records.length === 0) {
    throw createServiceError(404, 'No academic records found for this student and semester.');
  }

  const hasCompleteAssessments = STAGE_REQUIREMENTS[stage]
    .every((field) => records.every((record) => normalizeAssessment(record[field]) !== null));

  if (!attendance || !hasCompleteAssessments) {
    const message = stage === 'stage1'
      ? 'Stage 1 prediction requires attendance, Internal 1, and assignment data for all subjects.'
      : 'Stage 2 prediction requires attendance, Internal 1, Internal 2, and assignment data for all subjects.';
    throw createServiceError(400, message);
  }

  const inputs = {
    attendance: attendance.attendancePercentage,
    internal1: roundPercentage(averageAssessment(records, 'internal1')),
    assignment: roundPercentage(averageAssessment(records, 'assignment')),
  };

  if (stage === 'stage2') {
    inputs.internal2 = roundPercentage(averageAssessment(records, 'internal2'));
  }

  return inputs;
}

async function generatePrediction(studentId, semester, stage) {
  const inputs = await buildPredictionInputs(studentId, semester, stage);
  return postToMlService(`/predict/${stage}`, inputs, stage);
}

async function requestWhatIfPrediction(payload) {
  if (!payload || !['stage1', 'stage2'].includes(payload.stage)) {
    throw createServiceError(400, 'A valid prediction stage is required.');
  }

  const prediction = await postToMlService('/predict/what-if', payload, payload.stage);
  return prediction;
}

module.exports = {
  buildPredictionInputs,
  generatePrediction,
  requestWhatIfPrediction,
};