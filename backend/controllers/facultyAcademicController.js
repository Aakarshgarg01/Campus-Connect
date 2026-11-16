const mongoose = require('mongoose');
const AcademicRecord = require('../models/AcademicRecord');
const User = require('../models/user');

const assessmentFields = ['internal1', 'internal2', 'assignment'];
const createFields = ['studentId', 'semester', 'subjectName', ...assessmentFields];

function isRequestObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasOnlyFields(value, allowedFields) {
  return Object.keys(value).every((field) => allowedFields.includes(field));
}

function isValidAssessment(value) {
  return isRequestObject(value)
    && hasOnlyFields(value, ['obtained', 'maximum']);
}

function validateAssessments(body, fields) {
  return fields.every((field) => (
    !Object.hasOwn(body, field) || isValidAssessment(body[field])
  ));
}

function sendValidationError(response, error, message) {
  if (error.name !== 'ValidationError' && error.name !== 'CastError') {
    return false;
  }

  response.status(400).json({
    message,
    errors: error.name === 'ValidationError'
      ? Object.values(error.errors).map((validationError) => validationError.message)
      : [error.message],
  });
  return true;
}

async function createAcademicRecord(request, response) {
  const body = request.body;
  if (!isRequestObject(body) || !hasOnlyFields(body, createFields)) {
    return response.status(400).json({ message: 'Invalid academic record data' });
  }

  if (!mongoose.isObjectIdOrHexString(body.studentId)) {
    return response.status(400).json({ message: 'A valid studentId is required' });
  }

  if (!Number.isInteger(body.semester) || body.semester < 1) {
    return response.status(400).json({ message: 'Semester must be a positive integer' });
  }

  if (typeof body.subjectName !== 'string' || !body.subjectName.trim()) {
    return response.status(400).json({ message: 'subjectName is required' });
  }

  if (!validateAssessments(body, assessmentFields)) {
    return response.status(400).json({ message: 'Assessment data must contain only obtained and maximum values' });
  }

  const student = await User.findOne({ _id: body.studentId, role: 'student' }).select('_id');
  if (!student) {
    return response.status(404).json({ message: 'Student not found' });
  }

  try {
    const record = await AcademicRecord.create({
      studentId: student._id,
      semester: body.semester,
      subjectName: body.subjectName,
      ...(Object.hasOwn(body, 'internal1') ? { internal1: body.internal1 } : {}),
      ...(Object.hasOwn(body, 'internal2') ? { internal2: body.internal2 } : {}),
      ...(Object.hasOwn(body, 'assignment') ? { assignment: body.assignment } : {}),
    });

    return response.status(201).json({
      message: 'Academic record created',
      record,
    });
  } catch (error) {
    if (error.code === 11000) {
      return response.status(409).json({
        message: 'Academic record already exists for this student, semester, and subject.',
      });
    }
    if (sendValidationError(response, error, 'Invalid academic record data')) {
      return undefined;
    }
    throw error;
  }
}

async function updateAcademicRecord(request, response) {
  if (!mongoose.isObjectIdOrHexString(request.params.id)) {
    return response.status(400).json({ message: 'Invalid academic record id' });
  }

  const body = request.body;
  if (!isRequestObject(body)
    || Object.keys(body).length === 0
    || !hasOnlyFields(body, assessmentFields)
    || !validateAssessments(body, assessmentFields)) {
    return response.status(400).json({ message: 'Provide valid Internal 1, Internal 2, or Assignment data only' });
  }

  const record = await AcademicRecord.findById(request.params.id);
  if (!record) {
    return response.status(404).json({ message: 'Academic record not found' });
  }

  for (const field of assessmentFields) {
    if (Object.hasOwn(body, field)) {
      record[field] = body[field];
    }
  }

  try {
    await record.save();
    return response.status(200).json({
      message: 'Academic record updated',
      record,
    });
  } catch (error) {
    if (sendValidationError(response, error, 'Invalid academic record data')) {
      return undefined;
    }
    throw error;
  }
}

async function getAcademicRecordsForStudent(request, response) {
  const { studentId } = request.params;
  if (!mongoose.isObjectIdOrHexString(studentId)) {
    return response.status(400).json({ message: 'Invalid studentId' });
  }

  let semester;
  if (request.query.semester !== undefined) {
    const semesterValue = request.query.semester;
    semester = Number(semesterValue);
    if (typeof semesterValue !== 'string' || !Number.isInteger(semester) || semester < 1) {
      return response.status(400).json({ message: 'Semester must be a positive integer' });
    }
  }

  const student = await User.findOne({ _id: studentId, role: 'student' })
    .select('_id name rollNumber');
  if (!student) {
    return response.status(404).json({ message: 'Student not found' });
  }

  const filter = { studentId: student._id };
  if (semester !== undefined) {
    filter.semester = semester;
  }

  const records = await AcademicRecord.find(filter)
    .select('semester subjectName internal1 internal2 assignment')
    .sort({ subjectName: 1, semester: 1 })
    .lean();

  return response.status(200).json({
    student: {
      id: student._id.toString(),
      name: student.name,
      rollNumber: student.rollNumber,
    },
    semester: semester ?? null,
    records,
  });
}

module.exports = {
  createAcademicRecord,
  updateAcademicRecord,
  getAcademicRecordsForStudent,
};