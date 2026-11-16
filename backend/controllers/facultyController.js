const mongoose = require('mongoose');
const User = require('../models/user');
const AcademicRecord = require('../models/AcademicRecord');
const Attendance = require('../models/Attendance');
const Prediction = require('../models/Prediction');
const StudentTarget = require('../models/StudentTarget');
const Monitoring = require('../models/Monitoring');
const FacultyBenchmark = require('../models/FacultyBenchmark');

const VALID_MONITORING_STATUSES = [
  'Not Contacted',
  'Contacted',
  'Counselling Done',
  'Under Monitoring',
  'Improved',
];

function normalizeText(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function parsePositiveInteger(value) {
  if (typeof value !== 'string' || !/^\d+$/.test(value)) {
    return null;
  }

  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function toPercentage(obtained, maximum) {
  if (typeof obtained !== 'number' || typeof maximum !== 'number' || maximum <= 0) {
    return null;
  }

  const percentage = (obtained / maximum) * 100;
  return Number.isFinite(percentage) ? Number(percentage.toFixed(2)) : null;
}

function formatAssessment(assessment) {
  if (!assessment || typeof assessment !== 'object') {
    return null;
  }

  const percentage = toPercentage(assessment.obtained, assessment.maximum);
  if (percentage === null) {
    return null;
  }

  return {
    obtained: assessment.obtained,
    maximum: assessment.maximum,
    percentage,
  };
}

function buildStudentListItem(student) {
  return {
    id: student._id.toString(),
    name: student.name,
    email: student.email,
    rollNumber: student.rollNumber,
    department: student.department,
    semester: student.semester,
  };
}

function buildStudentDetail(profile) {
  return {
    id: profile._id.toString(),
    name: profile.name,
    email: profile.email,
    rollNumber: profile.rollNumber,
    department: profile.department,
    semester: profile.semester,
  };
}

async function getFacultyStudents(request, response) {
  const filter = { role: 'student' };

  if (request.query.semester !== undefined) {
    const semester = parsePositiveInteger(request.query.semester);
    if (semester === null) {
      return response.status(400).json({ message: 'Semester must be a positive integer.' });
    }
    filter.semester = semester;
  }

  if (request.query.department !== undefined) {
    const department = normalizeText(request.query.department);
    if (!department) {
      return response.status(400).json({ message: 'Department is required when supplied.' });
    }
    filter.department = department;
  }

  const students = await User.find(filter)
    .select('_id name email rollNumber department semester')
    .sort({ rollNumber: 1, _id: 1 })
    .lean();

  return response.status(200).json({
    students: students.map(buildStudentListItem),
  });
}

async function getFacultyStudentDetail(request, response) {
  const { studentId } = request.params;
  if (!mongoose.isObjectIdOrHexString(studentId)) {
    return response.status(400).json({ message: 'Invalid studentId' });
  }

  const student = await User.findOne({ _id: studentId, role: 'student' })
    .select('_id name email rollNumber department semester')
    .lean();

  if (!student) {
    return response.status(404).json({ message: 'Student not found' });
  }

  const semester = request.query.semester === undefined
    ? student.semester
    : parsePositiveInteger(request.query.semester);

  if (semester === null) {
    return response.status(400).json({ message: 'Semester must be a positive integer.' });
  }

  const [attendance, records, predictions, target, monitoring] = await Promise.all([
    Attendance.findOne({ studentId: student._id, semester }).select('attendancePercentage').lean(),
    AcademicRecord.find({ studentId: student._id, semester })
      .select('subjectName internal1 internal2 assignment')
      .sort({ subjectName: 1 })
      .lean(),
    Prediction.find({ studentId: student._id, semester })
      .select('stage predictedFinalPerformance createdAt')
      .sort({ createdAt: -1, _id: -1 })
      .lean(),
    StudentTarget.findOne({ studentId: student._id, semester }).select('targetPerformance').lean(),
    Monitoring.findOne({ studentId: student._id, semester }).select('status notes updatedAt').lean(),
  ]);

  return response.status(200).json({
    student: buildStudentDetail(student),
    attendance: attendance ? { percentage: attendance.attendancePercentage } : null,
    subjects: records.map((record) => ({
      subjectName: record.subjectName,
      internal1: formatAssessment(record.internal1),
      internal2: formatAssessment(record.internal2),
      assignment: formatAssessment(record.assignment),
    })),
    predictions: predictions.map((prediction) => ({
      stage: prediction.stage,
      predictedFinalPerformance: Number(prediction.predictedFinalPerformance.toFixed(2)),
      createdAt: prediction.createdAt,
    })),
    target: target ? { targetPerformance: target.targetPerformance } : null,
    monitoring: monitoring
      ? {
          status: monitoring.status,
          ...(monitoring.notes ? { notes: monitoring.notes } : {}),
        }
      : { status: 'Not Contacted' },
  });
}

async function getFacultyBenchmark(request, response) {
  const semester = request.query.semester === undefined
    ? undefined
    : parsePositiveInteger(request.query.semester);

  if (request.query.semester !== undefined && semester === null) {
    return response.status(400).json({ message: 'Semester must be a positive integer.' });
  }

  const department = request.query.department === undefined
    ? normalizeText((await User.findById(request.user.id).select('department').lean()?.department) || '')
    : normalizeText(request.query.department);

  if (request.query.department !== undefined && !department) {
    return response.status(400).json({ message: 'Department is required when supplied.' });
  }

  if (!department) {
    return response.status(404).json({ message: 'Benchmark not found' });
  }

  const filter = { department };
  if (semester !== undefined) {
    filter.semester = semester;
  }

  const benchmark = await FacultyBenchmark.findOne(filter)
    .sort({ semester: -1, createdAt: -1 })
    .lean();

  if (!benchmark) {
    return response.status(404).json({ message: 'Benchmark not found' });
  }

  return response.status(200).json({
    benchmark: {
      semester: benchmark.semester,
      department: benchmark.department,
      benchmarkPerformance: benchmark.benchmarkPerformance,
    },
  });
}

async function updateFacultyBenchmark(request, response) {
  const body = request.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)
    || Object.keys(body).some((field) => !['semester', 'department', 'benchmarkPerformance'].includes(field))) {
    return response.status(400).json({ message: 'Provide semester, department, and benchmarkPerformance.' });
  }

  const { semester, department, benchmarkPerformance } = body;

  if (!Number.isInteger(semester) || semester < 1) {
    return response.status(400).json({ message: 'Semester must be a positive integer.' });
  }

  const normalizedDepartment = normalizeText(department);
  if (!normalizedDepartment) {
    return response.status(400).json({ message: 'Department is required.' });
  }

  if (typeof benchmarkPerformance !== 'number'
    || !Number.isFinite(benchmarkPerformance)
    || benchmarkPerformance < 0
    || benchmarkPerformance > 100) {
    return response.status(400).json({ message: 'benchmarkPerformance must be between 0 and 100.' });
  }

  const benchmark = await FacultyBenchmark.findOneAndUpdate(
    { semester, department: normalizedDepartment },
    {
      $set: {
        benchmarkPerformance,
        createdBy: request.user.id,
      },
      $setOnInsert: {
        semester,
        department: normalizedDepartment,
      },
    },
    {
      new: true,
      upsert: true,
      runValidators: true,
      setDefaultsOnInsert: true,
    },
  );

  return response.status(200).json({
    message: 'Benchmark updated successfully',
    benchmark: {
      semester: benchmark.semester,
      department: benchmark.department,
      benchmarkPerformance: benchmark.benchmarkPerformance,
    },
  });
}

async function getMonitoringList(request, response) {
  const filter = { role: 'student' };

  const department = request.query.department === undefined
    ? undefined
    : normalizeText(request.query.department);

  if (request.query.department !== undefined && !department) {
    return response.status(400).json({ message: 'Department is required when supplied.' });
  }

  if (department) {
    filter.department = department;
  }

  let semesterFilter = request.query.semester === undefined
    ? undefined
    : parsePositiveInteger(request.query.semester);

  if (request.query.semester !== undefined && semesterFilter === null) {
    return response.status(400).json({ message: 'Semester must be a positive integer.' });
  }

  if (semesterFilter !== undefined) {
    filter.semester = semesterFilter;
  }

  const statusFilter = request.query.status === undefined
    ? undefined
    : normalizeText(request.query.status);

  if (request.query.status !== undefined && !VALID_MONITORING_STATUSES.includes(statusFilter)) {
    return response.status(400).json({ message: 'Invalid monitoring status.' });
  }

  const students = await User.find(filter)
    .select('_id name rollNumber department semester')
    .sort({ rollNumber: 1, _id: 1 })
    .lean();

  const semestersToCheck = new Set(
    students.map((student) => (semesterFilter ?? student.semester).toString()),
  );

  const monitoringDocs = await Monitoring.find({
    studentId: { $in: students.map((student) => student._id) },
    semester: { $in: Array.from(semestersToCheck).map(Number) },
  }).select('studentId semester status notes updatedAt').lean();

  const monitoringMap = new Map();
  for (const doc of monitoringDocs) {
    monitoringMap.set(`${doc.studentId.toString()}:${doc.semester}`, doc);
  }

  const items = students
    .map((student) => {
      const resolvedSemester = semesterFilter ?? student.semester;
      const existingMonitoring = monitoringMap.get(`${student._id.toString()}:${resolvedSemester}`);
      const status = existingMonitoring ? existingMonitoring.status : 'Not Contacted';

      if (statusFilter && status !== statusFilter) {
        return null;
      }

      return {
        student: {
          id: student._id.toString(),
          name: student.name,
          rollNumber: student.rollNumber,
          department: student.department,
          semester: student.semester,
        },
        monitoring: {
          status,
          ...(existingMonitoring && existingMonitoring.notes ? { notes: existingMonitoring.notes } : {}),
          ...(existingMonitoring && existingMonitoring.updatedAt ? { updatedAt: existingMonitoring.updatedAt } : {}),
        },
      };
    })
    .filter(Boolean);

  return response.status(200).json({ students: items });
}

async function updateMonitoring(request, response) {
  const { studentId } = request.params;
  if (!mongoose.isObjectIdOrHexString(studentId)) {
    return response.status(400).json({ message: 'Invalid studentId' });
  }

  const body = request.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)
    || Object.keys(body).some((field) => !['semester', 'status', 'notes'].includes(field))) {
    return response.status(400).json({ message: 'Provide semester, status, and optional notes.' });
  }

  const { semester, status, notes } = body;
  if (!Number.isInteger(semester) || semester < 1) {
    return response.status(400).json({ message: 'Semester must be a positive integer.' });
  }

  if (!VALID_MONITORING_STATUSES.includes(status)) {
    return response.status(400).json({ message: 'Invalid monitoring status.' });
  }

  const student = await User.findOne({ _id: studentId, role: 'student' }).select('_id').lean();
  if (!student) {
    return response.status(404).json({ message: 'Student not found' });
  }

  const monitoring = await Monitoring.findOneAndUpdate(
    { studentId: student._id, semester },
    {
      $set: {
        status,
        notes: typeof notes === 'string' ? notes.trim() : '',
        updatedBy: request.user.id,
      },
      $setOnInsert: {
        studentId: student._id,
        semester,
      },
    },
    {
      new: true,
      upsert: true,
      runValidators: true,
      setDefaultsOnInsert: true,
    },
  );

  return response.status(200).json({
    message: 'Monitoring status updated successfully',
    monitoring: {
      studentId: monitoring.studentId.toString(),
      semester: monitoring.semester,
      status: monitoring.status,
      notes: monitoring.notes || undefined,
    },
  });
}

module.exports = {
  getFacultyStudents,
  getFacultyStudentDetail,
  getFacultyBenchmark,
  updateFacultyBenchmark,
  getMonitoringList,
  updateMonitoring,
};
