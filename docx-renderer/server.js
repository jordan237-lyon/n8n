import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import PizZip from 'pizzip';
import Docxtemplater from 'docxtemplater';

const app = express();
const port = 3000;
const cvTemplatePath = '/files/templates/CV-template.docx';
const letterTemplatePath = '/files/templates/LM-template.docx';

const requiredFields = [
  'PROFIL',
  'COMPETENCES',
  'EXP1_POINT1',
  'EXP1_POINT2',
  'EXP1_POINT3',
  'EXP1_POINT4',
  'EXP1_POINT5',
  'EXP1_POINT6',
  'EXP2_POINT1',
  'EXP2_POINT2',
  'EXP2_POINT3',
  'EXP2_POINT4',
  'EXP2_POINT5',
  'EXP2_POINT6',
];

const requiredLetterFields = ['cover_letter'];

app.use(express.json({ limit: '1mb' }));

app.get('/health', (_request, response) => {
  response.json({ status: 'ok' });
});

function sanitizeFilename(requestedName, fallbackName) {
  return (
    path
      .basename(requestedName)
      .replace(/[^a-zA-Z0-9À-ÿ._-]/g, '-')
      .replace(/-+/g, '-')
      .slice(0, 120) || fallbackName
  );
}

function convertDocxToPdf(docxPath, temporaryDirectory) {
  const pdfPath = path.join(
    temporaryDirectory,
    `${path.parse(docxPath).name}.pdf`,
  );
  const profilePath = path.join(temporaryDirectory, 'libreoffice-profile');

  const conversion = spawnSync(
    'soffice',
    [
      '--headless',
      `-env:UserInstallation=file://${profilePath}`,
      '--convert-to',
      'pdf:writer_pdf_Export',
      '--outdir',
      temporaryDirectory,
      docxPath,
    ],
    {
      encoding: 'utf8',
      timeout: 60000,
      env: { ...process.env, HOME: temporaryDirectory },
    },
  );

  if (conversion.status !== 0 || !fs.existsSync(pdfPath)) {
    throw new Error(
      `Conversion PDF impossible: ${conversion.stderr || conversion.stdout}`,
    );
  }

  return fs.readFileSync(pdfPath);
}

function renderFromTemplate({
  request,
  response,
  templatePath,
  requiredFieldsList,
  fallbackName,
  pageCount,
}) {
  let temporaryDirectory;

  try {
    const data = request.body?.data;

    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      return response.status(400).json({
        error: 'Le champ data doit contenir un objet JSON.',
      });
    }

    const missingFields = requiredFieldsList.filter(
      (field) => typeof data[field] !== 'string' || !data[field].trim(),
    );

    if (missingFields.length > 0) {
      return response.status(400).json({
        error: 'Champs absents ou vides.',
        fields: missingFields,
      });
    }

    if (!fs.existsSync(templatePath)) {
      return response.status(500).json({
        error: `Le modèle ${path.basename(templatePath)} est introuvable.`,
      });
    }

    const template = fs.readFileSync(templatePath);
    const zip = new PizZip(template);

    const document = new Docxtemplater(zip, {
      paragraphLoop: true,
      linebreaks: true,
      delimiters: {
        start: '{{',
        end: '}}',
      },
    });

    document.render(data);

    const output = document.getZip().generate({
      type: 'nodebuffer',
      compression: 'DEFLATE',
    });

    const requestedName =
      typeof request.body.filename === 'string'
        ? request.body.filename
        : fallbackName;

    const safeName = sanitizeFilename(requestedName, fallbackName);

    const finalName = safeName.toLowerCase().endsWith('.pdf')
      ? safeName
      : `${safeName.replace(/\.docx$/i, '')}.pdf`;

    temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-render-'));
    const docxPath = path.join(temporaryDirectory, 'cv.docx');

    fs.writeFileSync(docxPath, output);

    if (typeof pageCount === 'number') {
      const pdfPath = path.join(temporaryDirectory, 'cv.pdf');
      const pdf = convertDocxToPdf(docxPath, temporaryDirectory);
      const pageInspection = spawnSync('pdfinfo', [pdfPath], {
        encoding: 'utf8',
        timeout: 10000,
      });
      const pageMatch = pageInspection.stdout.match(/^Pages:\s+(\d+)$/m);
      const actualPageCount = pageMatch ? Number(pageMatch[1]) : null;

      if (actualPageCount !== pageCount) {
        return response.status(422).json({
          error: `Le document généré ne respecte pas la contrainte de ${pageCount} pages.`,
          pageCount: actualPageCount,
          expectedPageCount: pageCount,
        });
      }

      response.setHeader('Content-Type', 'application/pdf');
      response.setHeader(
        'Content-Disposition',
        `attachment; filename="${finalName}"`,
      );

      return response.send(pdf);
    }

    const shouldReturnPdf =
      String(request.body?.outputFormat || 'pdf').toLowerCase() !== 'docx';

    if (shouldReturnPdf) {
      const pdf = convertDocxToPdf(docxPath, temporaryDirectory);
      const pdfName = finalName.toLowerCase().endsWith('.pdf')
        ? finalName
        : `${finalName.replace(/\.docx$/i, '')}.pdf`;

      response.setHeader('Content-Type', 'application/pdf');
      response.setHeader(
        'Content-Disposition',
        `attachment; filename="${pdfName}"`,
      );

      return response.send(pdf);
    }

    const docx = fs.readFileSync(docxPath);
    const docxName = finalName.toLowerCase().endsWith('.docx')
      ? finalName
      : `${finalName.replace(/\.pdf$/i, '')}.docx`;

    response.setHeader(
      'Content-Type',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    );
    response.setHeader(
      'Content-Disposition',
      `attachment; filename="${docxName}"`,
    );

    return response.send(docx);
  } catch (error) {
    console.error('Document rendering failed:', error);

    return response.status(500).json({
      error: 'La génération du document a échoué.',
      details: error instanceof Error ? error.message : String(error),
    });
  } finally {
    if (temporaryDirectory) {
      fs.rmSync(temporaryDirectory, { recursive: true, force: true });
    }
  }
}

app.post('/render', (request, response) => {
  return renderFromTemplate({
    request,
    response,
    templatePath: cvTemplatePath,
    requiredFieldsList: requiredFields,
    fallbackName: 'CV-personnalise.docx',
    pageCount: 2,
  });
});

app.post('/render-letter', (request, response) => {
  return renderFromTemplate({
    request,
    response,
    templatePath: letterTemplatePath,
    requiredFieldsList: requiredLetterFields,
    fallbackName: 'Lettre-de-motivation.docx',
  });
});

app.listen(port, '0.0.0.0', () => {
  console.log(`DOCX renderer listening on port ${port}`);
});
