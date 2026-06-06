const state = {
  answers: {},
  history: [],
  currentQuestion: null,
  selectedValue: undefined,
  consultationId: null,
};

const questionBox = document.getElementById("questionBox");
const answerList = document.getElementById("answerList");
const progressText = document.getElementById("progressText");
const resultPanel = document.getElementById("resultPanel");
const resultContent = document.getElementById("resultContent");
const nextBtn = document.getElementById("nextBtn");
const backBtn = document.getElementById("backBtn");

function displayValue(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return value;
}

function renderAnswers() {
  const entries = Object.entries(state.answers);
  if (entries.length === 0) {
    answerList.innerHTML = "No answers yet.";
    answerList.classList.add("muted");
    return;
  }
  answerList.classList.remove("muted");
  answerList.innerHTML = entries
    .map(([key, value]) => `<div><span>${key.replaceAll("_", " ")}</span><span>${displayValue(value)}</span></div>`)
    .join("");
}

function renderQuestion(question) {
  state.currentQuestion = question;
  state.selectedValue = undefined;
  nextBtn.textContent = "Next";
  resultPanel.classList.add("hidden");

  if (!question) {
    questionBox.innerHTML = `
      <div class="question-card">
        <h2>Questionnaire completed</h2>
        <p class="muted">Click Generate Diagnosis to run the rule-based inference engine and save this consultation.</p>
      </div>`;
    nextBtn.textContent = "Generate Diagnosis";
    progressText.textContent = "All required questions answered.";
    return;
  }

  progressText.textContent = `Question ${Object.keys(state.answers).length + 1}`;
  let optionsHtml = "";

  if (question.type === "boolean") {
    optionsHtml = `
      <div class="option-list">
        <button class="option-button" data-value="true">Yes</button>
        <button class="option-button" data-value="false">No</button>
      </div>`;
  } else if (question.type === "select") {
    optionsHtml = `
      <div class="option-list">
        ${question.options.map(option => `<button class="option-button" data-value="${option}">${option}</button>`).join("")}
      </div>`;
  }

  questionBox.innerHTML = `
    <div class="question-card">
      <h2>${question.text}</h2>
      ${optionsHtml}
    </div>`;

  questionBox.querySelectorAll(".option-button").forEach(button => {
    button.addEventListener("click", () => {
      questionBox.querySelectorAll(".option-button").forEach(item => item.classList.remove("selected"));
      button.classList.add("selected");
      const rawValue = button.dataset.value;
      state.selectedValue = rawValue === "true" ? true : rawValue === "false" ? false : rawValue;
    });
  });
}

async function getStartQuestion() {
  const response = await fetch("/api/questions/start");
  const data = await response.json();
  renderQuestion(data.question);
  renderAnswers();
}

async function getNextQuestion() {
  const response = await fetch("/api/questions/next", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers: state.answers }),
  });
  const data = await response.json();
  renderQuestion(data.question);
  renderAnswers();
}

async function generateDiagnosis() {
  nextBtn.disabled = true;
  nextBtn.textContent = "Generating...";
  const response = await fetch("/api/diagnose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers: state.answers }),
  });
  const data = await response.json();
  nextBtn.disabled = false;
  nextBtn.textContent = "Generate Diagnosis";

  if (!response.ok) {
    resultPanel.classList.remove("hidden");
    resultContent.innerHTML = `<div class="alert error">${data.error || "Unable to generate diagnosis."}</div>`;
    return;
  }

  state.consultationId = data.consultation_id;
  const result = data.result;
  resultPanel.classList.remove("hidden");
  resultContent.innerHTML = `
    <div class="confidence-row">
      <span>${result.decision}</span>
      <span class="confidence">${result.confidence}%</span>
    </div>
    <p>${result.summary}</p>
    <h3>Recommendation</h3>
    <p>${result.recommendation}</p>
    <h3>Severity note</h3>
    <p>${result.severity_note}</p>
    <h3>Expert note</h3>
    <p>${result.expert_note}</p>
    <div class="hero-actions">
      <a class="button secondary" href="/consultations/${state.consultationId}">View saved result</a>
      <a class="button secondary" href="/consultations/${state.consultationId}/export.json">Export JSON</a>
      <a class="button secondary" href="/consultations/${state.consultationId}/export.csv">Export CSV</a>
    </div>
  `;
}

nextBtn.addEventListener("click", async () => {
  if (!state.currentQuestion) {
    await generateDiagnosis();
    return;
  }
  if (state.selectedValue === undefined) {
    alert("Please choose an answer before continuing.");
    return;
  }
  state.history.push({ question: state.currentQuestion, answers: { ...state.answers } });
  state.answers[state.currentQuestion.id] = state.selectedValue;
  await getNextQuestion();
});

backBtn.addEventListener("click", () => {
  const previous = state.history.pop();
  if (!previous) return;
  state.answers = previous.answers;
  renderQuestion(previous.question);
  renderAnswers();
});

getStartQuestion();
