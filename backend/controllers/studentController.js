const AcademicRecord = require('../models/AcademicRecord');
const Attendance = require('../models/Attendance');
const Prediction = require('../models/Prediction');
const StudentTarget = require('../models/StudentTarget');
const User = require('../models/user');

const BAND_PERCENT = 10;

function hasStudentIdOverride(request) {
  return Object.hasOwn(request.query || {}, 'studentId')
    || Object.hasOwn(request.body || {}, 'studentId');
}

function rejectStudentIdOverride(request, response) {
  if (!hasStudentIdOverride(request)) {
    return false;
  }

  response.status(400).json({ message: 'studentId must not be supplied; the authenticated student is used.' });
  return true;
}

function parseQuerySemester(value) {
  if (typeof value !== 'string' || !/^\d+$/.test(value)) {
    return null;
  }

  const semester = Number(value);
  return Number.isInteger(semester) && semester > 0 ? semester : null;
}

async function findAuthenticatedStudent(request, response) {
  const student = await User.findOne({ _id: request.user.id, role: 'student' })
    .select('_id name email role rollNumber department semester')
    .lean();

  if (!student) {
    response.status(404).json({ message: 'Student not found' });
    return null;
  }

  return student;
}

function resolveSemester(request, response, student) {
  if (request.query.semester === undefined) {
    return student.semester;
  }

  const semester = parseQuerySemester(request.query.semester);
  if (semester === null) {
    response.status(400).json({ message: 'Semester must be a positive integer.' });
    return null;
  }

  return semester;
}

function roundToTwo(value) {
  return Number(value.toFixed(2));
}

function getRawAssessmentPercentage(assessment) {
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

function getAssessmentPercentage(assessment) {
  const percentage = getRawAssessmentPercentage(assessment);
  return percentage === null ? null : roundToTwo(percentage);
}

function formatAssessment(assessment) {
  const percentage = getAssessmentPercentage(assessment);
  if (percentage === null) {
    return null;
  }

  return {
    obtained: assessment.obtained,
    maximum: assessment.maximum,
    percentage,
  };
}

async function getProfile(request, response) {
  if (rejectStudentIdOverride(request, response)) {
    return undefined;
  }

  const student = await findAuthenticatedStudent(request, response);
  if (!student) {
    return undefined;
  }

  return response.status(200).json({
    profile: {
      id: student._id.toString(),
      name: student.name,
      email: student.email,
      role: student.role,
      rollNumber: student.rollNumber,
      department: student.department,
      semester: student.semester,
    },
  });
}

async function getPerformance(request, response) {
  if (rejectStudentIdOverride(request, response)) {
    return undefined;
  }

  const student = await findAuthenticatedStudent(request, response);
  if (!student) {
    return undefined;
  }

  const semester = resolveSemester(request, response, student);
  if (semester === null) {
    return undefined;
  }

  const filter = { studentId: student._id, semester };
  const [records, attendance, predictions, target] = await Promise.all([
    AcademicRecord.find(filter)
      .select('subjectName internal1 internal2 assignment')
      .sort({ subjectName: 1 })
      .lean(),
    Attendance.findOne(filter).select('attendancePercentage').lean(),
    Prediction.find(filter)
      .select('stage predictedFinalPerformance createdAt')
      .sort({ createdAt: -1, _id: -1 })
      .lean(),
    StudentTarget.findOne(filter).select('targetPerformance').lean(),
  ]);

  return response.status(200).json({
    semester,
    attendance: attendance ? { percentage: attendance.attendancePercentage } : null,
    subjects: records.map((record) => ({
      subjectName: record.subjectName,
      internal1: formatAssessment(record.internal1),
      internal2: formatAssessment(record.internal2),
      assignment: formatAssessment(record.assignment),
    })),
    predictions: predictions.map((prediction) => ({
      stage: prediction.stage,
      predictedFinalPerformance: roundToTwo(prediction.predictedFinalPerformance),
      createdAt: prediction.createdAt,
    })),
    target: target ? { targetPerformance: target.targetPerformance } : null,
  });
}

async function getTarget(request, response) {
  if (rejectStudentIdOverride(request, response)) {
    return undefined;
  }

  const student = await findAuthenticatedStudent(request, response);
  if (!student) {
    return undefined;
  }

  const semester = resolveSemester(request, response, student);
  if (semester === null) {
    return undefined;
  }

  const target = await StudentTarget.findOne({ studentId: student._id, semester })
    .select('semester targetPerformance')
    .lean();

  return response.status(200).json({
    target: target
      ? { semester: target.semester, targetPerformance: target.targetPerformance }
      : null,
  });
}

async function updateTarget(request, response) {
  if (rejectStudentIdOverride(request, response)) {
    return undefined;
  }

  const body = request.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)
    || Object.keys(body).some((key) => !['semester', 'targetPerformance'].includes(key))) {
    return response.status(400).json({ message: 'Provide only semester and targetPerformance.' });
  }

  const { semester, targetPerformance } = body;
  if (!Number.isInteger(semester) || semester < 1) {
    return response.status(400).json({ message: 'Semester must be a positive integer.' });
  }

  if (typeof targetPerformance !== 'number'
    || !Number.isFinite(targetPerformance)
    || targetPerformance < 0
    || targetPerformance > 100) {
    return response.status(400).json({ message: 'targetPerformance must be a percentage between 0 and 100.' });
  }

  const student = await findAuthenticatedStudent(request, response);
  if (!student) {
    return undefined;
  }

  const filter = { studentId: student._id, semester };
  const update = {
    $set: { targetPerformance },
    $setOnInsert: filter,
  };

  let target;
  try {
    target = await StudentTarget.findOneAndUpdate(filter, update, {
      new: true,
      upsert: true,
      runValidators: true,
      setDefaultsOnInsert: true,
    });
  } catch (error) {
    if (error.code !== 11000) {
      throw error;
    }
    target = await StudentTarget.findOneAndUpdate(
      filter,
      { $set: { targetPerformance } },
      { new: true, runValidators: true },
    );
  }

  return response.status(200).json({
    message: 'Target updated successfully',
    target: {
      semester: target.semester,
      targetPerformance: target.targetPerformance,
    },
  });
}

function makeImprovementEntry(record) {
  const internal1Percentage = getRawAssessmentPercentage(record.internal1);
  if (internal1Percentage === null) {
    return {
      subjectName: record.subjectName,
      subjectAverage: null,
      status: 'insufficient_data',
      message: 'Internal 1 data is required.',
    };
  }

  const internal2Percentage = record.internal2 === undefined
    ? null
    : getRawAssessmentPercentage(record.internal2);
  if (record.internal2 !== undefined && internal2Percentage === null) {
    return {
      subjectName: record.subjectName,
      subjectAverage: null,
      status: 'insufficient_data',
      message: 'Valid Internal 2 data is required.',
    };
  }

  const rawSubjectAverage = internal2Percentage === null
    ? internal1Percentage
    : (internal1Percentage + internal2Percentage) / 2;

  return {
    subjectName: record.subjectName,
    subjectAverage: roundToTwo(rawSubjectAverage),
    rawSubjectAverage,
  };
}

async function getImprovementZone(request, response) {
  if (rejectStudentIdOverride(request, response)) {
    return undefined;
  }

  const student = await findAuthenticatedStudent(request, response);
  if (!student) {
    return undefined;
  }

  const semester = resolveSemester(request, response, student);
  if (semester === null) {
    return undefined;
  }

  const records = await AcademicRecord.find({ studentId: student._id, semester })
    .select('subjectName internal1 internal2')
    .sort({ subjectName: 1 })
    .lean();

  if (records.length === 0) {
    return response.status(200).json({
      semester,
      overallSubjectAverage: null,
      thresholds: null,
      subjects: [],
    });
  }

  const subjects = records.map(makeImprovementEntry);
  const completeSubjects = subjects.filter((subject) => subject.rawSubjectAverage !== undefined);

  if (completeSubjects.length === 0) {
    return response.status(200).json({
      semester,
      overallSubjectAverage: null,
      thresholds: null,
      subjects,
    });
  }

  const unroundedOverallAverage = completeSubjects.reduce(
    (total, subject) => total + subject.rawSubjectAverage,
    0,
  ) / completeSubjects.length;
  const lowerThreshold = unroundedOverallAverage * (1 - BAND_PERCENT / 100);
  const upperThreshold = unroundedOverallAverage * (1 + BAND_PERCENT / 100);

  for (const subject of completeSubjects) {
    if (subject.rawSubjectAverage < lowerThreshold) {
      subject.status = 'red';
      subject.message = 'Needs significant improvement';
    } else if (subject.rawSubjectAverage > upperThreshold) {
      subject.status = 'green';
      subject.message = 'Performing well';
    } else {
      subject.status = 'yellow';
      subject.message = 'Requires continued effort';
    }
  }

  return response.status(200).json({
    semester,
    overallSubjectAverage: roundToTwo(unroundedOverallAverage),
    thresholds: {
      lower: roundToTwo(lowerThreshold),
      upper: roundToTwo(upperThreshold),
    },
    subjects: subjects.map(({ rawSubjectAverage, ...subject }) => subject),
  });
}

module.exports = {
  getProfile,
  getPerformance,
  getTarget,
  updateTarget,
  getImprovementZone,
};