const mongoose = require('mongoose');
const Attendance = require('../models/Attendance');
const User = require('../models/user');

function isRequestObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function sendValidationError(response, error) {
  if (error.name !== 'ValidationError' && error.name !== 'CastError') {
    return false;
  }

  response.status(400).json({
    message: 'Invalid attendance data',
    errors: error.name === 'ValidationError'
      ? Object.values(error.errors).map((validationError) => validationError.message)
      : [error.message],
  });
  return true;
}

async function createOrUpdateAttendance(request, response) {
  const body = request.body;
  const allowedFields = ['studentId', 'semester', 'attendancePercentage'];
  if (!isRequestObject(body)
    || Object.keys(body).some((field) => !allowedFields.includes(field))) {
    return response.status(400).json({ message: 'Invalid attendance data' });
  }

  if (!mongoose.isObjectIdOrHexString(body.studentId)) {
    return response.status(400).json({ message: 'A valid studentId is required' });
  }

  if (!Number.isInteger(body.semester) || body.semester < 1) {
    return response.status(400).json({ message: 'Semester must be a positive integer' });
  }

  const student = await User.findOne({ _id: body.studentId, role: 'student' }).select('_id');
  if (!student) {
    return response.status(404).json({ message: 'Student not found' });
  }

  const filter = { studentId: student._id, semester: body.semester };
  try {
    await new Attendance({
      ...filter,
      attendancePercentage: body.attendancePercentage,
    }).validate();

    const attendance = await Attendance.findOneAndUpdate(
      filter,
      {
        $set: { attendancePercentage: body.attendancePercentage },
        $setOnInsert: filter,
      },
      { new: true, upsert: true, runValidators: true, setDefaultsOnInsert: true },
    );

    return response.status(200).json({
      message: 'Attendance saved',
      attendance,
    });
  } catch (error) {
    if (error.code === 11000) {
      const attendance = await Attendance.findOneAndUpdate(
        filter,
        { $set: { attendancePercentage: body.attendancePercentage } },
        { new: true, runValidators: true },
      );
      if (attendance) {
        return response.status(200).json({ message: 'Attendance saved', attendance });
      }
    }
    if (sendValidationError(response, error)) {
      return undefined;
    }
    throw error;
  }
}

module.exports = { createOrUpdateAttendance };