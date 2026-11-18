const crypto = require('node:crypto');
const path = require('node:path');
const XLSX = require('xlsx');
const mongoose = require('mongoose');
const User = require('../models/user');
const AcademicRecord = require('../models/AcademicRecord');
const Attendance = require('../models/Attendance');

const TEMP_UPLOADS = new Map();
const TEMP_UPLOAD_TTL_MS = 10 * 60 * 1000;
const ALLOWED_EXTENSIONS = new Set(['.csv', '.xls', '.xlsx']);

function canonicalizeHeader(value) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeText(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function normalizeName(value) {
  return normalizeText(String(value ?? '')).replace(/\s+/g, ' ');
}

function toNumber(value) {
  if (value === undefined || value === null) {
    return null;
  }

  const normalized = String(value).trim();
  if (normalized === '') {
    return null;
  }

  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function parsePositiveInteger(value) {
  const numeric = toNumber(value);
  if (numeric === null) {
    return null;
  }

  return Number.isInteger(numeric) && numeric > 0 ? numeric : null;
}

function createValidationError(row, field, message) {
  return { row, field, message };
}

function getRowValue(rowObject, fieldNames) {
  for (const fieldName of fieldNames) {
    if (Object.prototype.hasOwnProperty.call(rowObject, fieldName)) {
      return rowObject[fieldName];
    }
  }
  return undefined;
}

function readWorkbookRows(file) {
  if (!file || !file.buffer || file.buffer.length === 0) {
    throw new Error('Uploaded file is empty or unreadable.');
  }

  const extension = path.extname(file.originalname || '').toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(extension)) {
    throw new Error('Unsupported file type. Upload a CSV, XLS, or XLSX file.');
  }

  const workbook = XLSX.read(file.buffer, { type: 'buffer' });
  const firstSheetName = workbook.SheetNames[0];
  const firstSheet = workbook.Sheets[firstSheetName];
  if (!firstSheet) {
    throw new Error('Uploaded file does not contain any readable worksheet.');
  }

  const rows = XLSX.utils.sheet_to_json(firstSheet, { defval: '', raw: false, blankrows: false });
  if (rows.length === 0) {
    throw new Error('Uploaded file does not contain any rows.');
  }

  const headerKeys = Object.keys(rows[0]).map(canonicalizeHeader);
  const duplicateHeaders = headerKeys.filter((header, index, list) => header && list.indexOf(header) !== index);
  if (duplicateHeaders.length > 0) {
    throw new Error(`Ambiguous header mapping for '${duplicateHeaders[0]}'.`);
  }

  const requiredHeaders = ['roll no', 'student', 'semester', 'subject', 'attendance'];
  const missingHeaders = requiredHeaders.filter((header) => !headerKeys.includes(header));
  if (missingHeaders.length > 0) {
    throw new Error(`Missing required columns: ${missingHeaders.join(', ')}.`);
  }

  return rows.map((row, index) => ({
    rowNumber: index + 2,
    values: Object.fromEntries(Object.entries(row).map(([key, value]) => [canonicalizeHeader(key), value])),
  }));
}

function buildPreviewRow(rowNumber, student, semester, subject, internal1, internal2, assignment, attendance) {
  const preview = {
    row: rowNumber,
    rollNumber: student.rollNumber,
    student: student.name,
    semester,
    subject,
  };

  if (internal1) {
    preview.internal1 = { obtained: internal1.obtained, maximum: internal1.maximum };
  }

  if (internal2) {
    preview.internal2 = { obtained: internal2.obtained, maximum: internal2.maximum };
  }

  if (assignment) {
    preview.assignment = { obtained: assignment.obtained, maximum: assignment.maximum };
  }

  if (attendance !== null && attendance !== undefined) {
    preview.attendance = attendance;
  }

  return preview;
}

function isEmptyRow(values) {
  return Object.values(values).every((value) => normalizeText(String(value ?? '')).length === 0);
}

async function validateRows(rows, requestSemester) {
  const errors = [];
  const validPreview = [];
  const seenAcademicKeys = new Set();
  const attendanceGroups = new Map();

  for (const row of rows) {
    if (isEmptyRow(row.values)) {
      continue;
    }

    const rowNumber = row.rowNumber;
    const rollNumberValue = getRowValue(row.values, ['roll no', 'rollnumber', 'roll number']);
    const studentNameValue = getRowValue(row.values, ['student', 'name']);
    const semesterValue = getRowValue(row.values, ['semester']);
    const subjectValue = getRowValue(row.values, ['subject', 'subject name', 'course']);
    const attendanceValue = getRowValue(row.values, ['attendance', 'attendance percentage', 'attendance %']);

    const rollNumber = normalizeText(String(rollNumberValue ?? '')).toUpperCase();
    const studentName = normalizeName(studentNameValue);
    const parsedSemester = parsePositiveInteger(semesterValue ?? requestSemester);
    const subjectName = normalizeName(subjectValue);
    const attendanceNumber = toNumber(attendanceValue);

    if (!rollNumber) {
      errors.push(createValidationError(rowNumber, 'Roll No', 'Roll No is required.'));
    }

    if (!studentName) {
      errors.push(createValidationError(rowNumber, 'Student', 'Student name is required.'));
    }

    if (parsedSemester === null) {
      errors.push(createValidationError(rowNumber, 'Semester', 'Semester is required and must be a positive integer.'));
    }

    if (!subjectName) {
      errors.push(createValidationError(rowNumber, 'Subject', 'Subject is required.'));
    }

    if (attendanceNumber === null || attendanceNumber < 0 || attendanceNumber > 100) {
      errors.push(createValidationError(rowNumber, 'Attendance', 'Attendance must be a number between 0 and 100.'));
    }

    let student = null;
    if (rollNumber) {
      student = await User.findOne({ rollNumber }).select('_id name role rollNumber');
      if (!student || student.role !== 'student') {
        errors.push(createValidationError(rowNumber, 'Roll No', `Student with roll number ${rollNumber} was not found.`));
      } else if (studentName && normalizeName(student.name) !== normalizeName(studentName)) {
        errors.push(createValidationError(rowNumber, 'Student', `Student name does not match the registered record for roll number ${rollNumber}.`));
      }
    }

    const internal1Obtained = toNumber(getRowValue(row.values, ['internal 1 obtained', 'internal1 obtained', 'internal one obtained', 'internal 1 marks obtained']));
    const internal1Maximum = toNumber(getRowValue(row.values, ['internal 1 maximum', 'internal1 maximum', 'internal one maximum', 'internal 1 marks maximum']));
    const internal2Obtained = toNumber(getRowValue(row.values, ['internal 2 obtained', 'internal2 obtained']));
    const internal2Maximum = toNumber(getRowValue(row.values, ['internal 2 maximum', 'internal2 maximum']));
    const assignmentObtained = toNumber(getRowValue(row.values, ['assignment obtained', 'assignments obtained', 'assignment marks obtained']));
    const assignmentMaximum = toNumber(getRowValue(row.values, ['assignment maximum', 'assignment marks maximum']));

    const hasInternal1 = internal1Obtained !== null || internal1Maximum !== null;
    if (hasInternal1) {
      if (internal1Obtained === null || internal1Maximum === null) {
        errors.push(createValidationError(rowNumber, 'Internal 1', 'Internal 1 obtained and maximum values must be supplied together.'));
      } else if (internal1Obtained < 0) {
        errors.push(createValidationError(rowNumber, 'Internal 1 Obtained', 'Internal 1 obtained marks cannot be negative.'));
      } else if (internal1Maximum <= 0) {
        errors.push(createValidationError(rowNumber, 'Internal 1 Maximum', 'Internal 1 maximum marks must be greater than 0.'));
      } else if (internal1Obtained > internal1Maximum) {
        errors.push(createValidationError(rowNumber, 'Internal 1 Obtained', 'Obtained marks cannot exceed maximum marks.'));
      }
    } else {
      errors.push(createValidationError(rowNumber, 'Internal 1 Obtained', 'Internal 1 marks are required.'));
    }

    const hasAssignment = assignmentObtained !== null || assignmentMaximum !== null;
    if (hasAssignment) {
      if (assignmentObtained === null || assignmentMaximum === null) {
        errors.push(createValidationError(rowNumber, 'Assignment', 'Assignment obtained and maximum values must be supplied together.'));
      } else if (assignmentObtained < 0) {
        errors.push(createValidationError(rowNumber, 'Assignment Obtained', 'Assignment obtained marks cannot be negative.'));
      } else if (assignmentMaximum <= 0) {
        errors.push(createValidationError(rowNumber, 'Assignment Maximum', 'Assignment maximum marks must be greater than 0.'));
      } else if (assignmentObtained > assignmentMaximum) {
        errors.push(createValidationError(rowNumber, 'Assignment Obtained', 'Obtained marks cannot exceed maximum marks.'));
      }
    } else {
      errors.push(createValidationError(rowNumber, 'Assignment Obtained', 'Assignment marks are required.'));
    }

    const hasInternal2 = internal2Obtained !== null || internal2Maximum !== null;
    if (hasInternal2) {
      if (internal2Obtained === null || internal2Maximum === null) {
        errors.push(createValidationError(rowNumber, 'Internal 2', 'Internal 2 obtained and maximum values must be supplied together.'));
      } else if (internal2Obtained < 0) {
        errors.push(createValidationError(rowNumber, 'Internal 2 Obtained', 'Internal 2 obtained marks cannot be negative.'));
      } else if (internal2Maximum <= 0) {
        errors.push(createValidationError(rowNumber, 'Internal 2 Maximum', 'Internal 2 maximum marks must be greater than 0.'));
      } else if (internal2Obtained > internal2Maximum) {
        errors.push(createValidationError(rowNumber, 'Internal 2 Obtained', 'Obtained marks cannot exceed maximum marks.'));
      }
    }

    if (student && parsedSemester !== null && subjectName) {
      const academicKey = `${student._id.toString()}:${parsedSemester}:${subjectName.toLowerCase()}`;
      if (seenAcademicKeys.has(academicKey)) {
        errors.push(createValidationError(rowNumber, 'Subject', 'Duplicate student-subject-semester record in uploaded file.'));
      } else {
        seenAcademicKeys.add(academicKey);
      }
    }

    if (student && parsedSemester !== null && attendanceNumber !== null) {
      const attendanceKey = `${student._id.toString()}:${parsedSemester}`;
      if (!attendanceGroups.has(attendanceKey)) {
        attendanceGroups.set(attendanceKey, { rows: [], values: new Set() });
      }

      const group = attendanceGroups.get(attendanceKey);
      group.rows.push(rowNumber);
      group.values.add(attendanceNumber);
    }

    if (!student || !subjectName || parsedSemester === null || attendanceNumber === null) {
      continue;
    }

    if (internal1Obtained === null || internal1Maximum === null || assignmentObtained === null || assignmentMaximum === null) {
      continue;
    }

    validPreview.push(buildPreviewRow(
      rowNumber,
      student,
      parsedSemester,
      subjectName,
      { obtained: internal1Obtained, maximum: internal1Maximum },
      internal2Obtained !== null && internal2Maximum !== null ? { obtained: internal2Obtained, maximum: internal2Maximum } : undefined,
      { obtained: assignmentObtained, maximum: assignmentMaximum },
      attendanceNumber,
    ));
  }

  for (const group of attendanceGroups.values()) {
    if (group.values.size > 1) {
      const message = 'Conflicting attendance values for student and semester.';
      group.rows.forEach((rowNumber) => {
        errors.push(createValidationError(rowNumber, 'Attendance', message));
      });
    }
  }

  const uniqueErrorRows = new Set(errors.map((error) => error.row));
  return {
    valid: errors.length === 0,
    summary: {
      totalRows: rows.filter((row) => !isEmptyRow(row.values)).length,
      validRows: validPreview.length,
      errorRows: uniqueErrorRows.size,
      students: new Set(validPreview.map((previewRow) => previewRow.rollNumber)).size,
      subjects: new Set(validPreview.map((previewRow) => previewRow.subject)).size,
    },
    errors,
    preview: errors.length === 0 ? validPreview : [],
    rows: errors.length === 0 ? validPreview : [],
  };
}

function createUploadReference(payload) {
  const uploadId = crypto.randomUUID();
  TEMP_UPLOADS.set(uploadId, {
    payload,
    expiresAt: Date.now() + TEMP_UPLOAD_TTL_MS,
    used: false,
  });

  return uploadId;
}

function getTemporaryUpload(uploadId) {
  const upload = TEMP_UPLOADS.get(uploadId);
  if (!upload) {
    throw new Error('Upload reference not found or invalid.');
  }

  if (upload.used) {
    throw new Error('This upload reference has already been used.');
  }

  if (Date.now() > upload.expiresAt) {
    TEMP_UPLOADS.delete(uploadId);
    throw new Error('This upload reference has expired.');
  }

  return upload;
}

async function previewBulkAcademicUpload(file, requestSemester) {
  const parsedRows = readWorkbookRows(file);
  const validation = await validateRows(parsedRows, requestSemester);

  if (!validation.valid) {
    return {
      valid: false,
      summary: validation.summary,
      errors: validation.errors,
      preview: [],
    };
  }

  const uploadId = createUploadReference(validation);
  return {
    valid: true,
    uploadId,
    summary: validation.summary,
    errors: [],
    preview: validation.preview,
  };
}

async function confirmBulkAcademicUpload(uploadId) {
  const upload = getTemporaryUpload(uploadId);
  const uploadPayload = upload.payload;
  upload.used = true;
  TEMP_UPLOADS.delete(uploadId);

  const rows = uploadPayload.rows;
  const attendanceMap = new Map();
  let academicRecordsCreated = 0;
  let academicRecordsUpdated = 0;
  let attendanceCreated = 0;
  let attendanceUpdated = 0;

  const topologyType = mongoose.connection.client.topology.description.type;
  const supportsTransactions = topologyType === 'ReplicaSetWithPrimary' || topologyType === 'Sharded';
  const session = supportsTransactions ? await mongoose.startSession() : null;
  try {
    const persistRows = async () => {
      for (const row of rows) {
        const student = await User.findOne({ rollNumber: String(row.rollNumber).toUpperCase() }).session(session).select('_id role');
        if (!student || student.role !== 'student') {
          throw new Error(`Student with roll number ${row.rollNumber} was not found.`);
        }

        const academicRecordQuery = {
          studentId: student._id,
          semester: row.semester,
          subjectName: row.subject,
        };

        const existingAcademicRecord = await AcademicRecord.findOne(academicRecordQuery).session(session);
        const updateData = {};

        if (row.internal1) {
          updateData.internal1 = {
            obtained: row.internal1.obtained,
            maximum: row.internal1.maximum,
          };
        }

        if (row.internal2) {
          updateData.internal2 = {
            obtained: row.internal2.obtained,
            maximum: row.internal2.maximum,
          };
        }

        if (row.assignment) {
          updateData.assignment = {
            obtained: row.assignment.obtained,
            maximum: row.assignment.maximum,
          };
        }

        if (existingAcademicRecord) {
          academicRecordsUpdated += 1;
          await AcademicRecord.updateOne(
            { _id: existingAcademicRecord._id },
            { $set: updateData },
            { session },
          );
        } else {
          academicRecordsCreated += 1;
          await AcademicRecord.create([{ ...academicRecordQuery, ...updateData }], { session });
        }

        const attendanceKey = `${student._id.toString()}:${row.semester}`;
        attendanceMap.set(attendanceKey, row.attendance);
      }

      for (const [attendanceKey, attendanceValue] of attendanceMap.entries()) {
        const [studentId, semesterText] = attendanceKey.split(':');
        const semester = Number(semesterText);
        const existingAttendance = await Attendance.findOne({ studentId, semester }).session(session);

        if (!existingAttendance) {
          await Attendance.create([{ studentId, semester, attendancePercentage: attendanceValue }], { session });
          attendanceCreated += 1;
        } else {
          await Attendance.updateOne(
            { _id: existingAttendance._id },
            { $set: { attendancePercentage: attendanceValue } },
            { session },
          );
          attendanceUpdated += 1;
        }
      }
    };

    if (session) {
      await session.withTransaction(persistRows);
    } else {
      await persistRows();
    }
  } finally {
    if (session) {
      await session.endSession();
    }
  }

  return {
    message: 'Bulk academic upload completed successfully',
    summary: {
      rowsProcessed: rows.length,
      academicRecordsCreated,
      academicRecordsUpdated,
      attendanceCreated,
      attendanceUpdated,
    },
  };
}

module.exports = {
  previewBulkAcademicUpload,
  confirmBulkAcademicUpload,
  TEMP_UPLOADS,
  TEMP_UPLOAD_TTL_MS,
};
