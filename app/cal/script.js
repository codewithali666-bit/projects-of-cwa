const expressionEl = document.getElementById('expression');
const resultEl = document.getElementById('result');
const buttons = document.querySelectorAll('.btn');
const membershipBadge = document.getElementById('membershipBadge');
const membershipText = document.getElementById('membershipText');

let expression = '';
let currentInput = '0';
let justCalculated = false;
let isPremium = false;
let pendingCorrectResult = null;
let pendingWrongResult = null;
let pendingPrettyExpr = '';

const planPrices = {
  weekly:  { label: 'Weekly',  amount: '44,000', raw: 44000 },
  monthly: { label: 'Monthly', amount: '60,000', raw: 60000 },
  yearly:  { label: 'Yearly',  amount: '95,000', raw: 95000 },
};
let selectedPlan = 'weekly';

/* ---------- Display helpers ---------- */

function formatNumber(numStr) {
  if (numStr === '' || numStr === '-' || numStr === '.' || numStr === 'Error') return numStr;
  if (numStr.includes('e')) return numStr;
  const parts = numStr.split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return parts.join('.');
}

function updateCurrentDisplay() {
  resultEl.textContent = currentInput;
}

function updateExpressionDisplay() {
  const pretty = expression
    .replace(/\*/g, '×')
    .replace(/\//g, '÷')
    .replace(/-/g, '−');
  expressionEl.textContent = pretty || '\u00A0';
}

function isOperator(ch) {
  return ch === '+' || ch === '-' || ch === '*' || ch === '/' || ch === '%';
}

function setPremiumBadge() {
  if (!membershipBadge || !membershipText) return;
  if (isPremium) {
    membershipBadge.classList.add('premium');
    membershipText.textContent = 'PREMIUM';
  } else {
    membershipBadge.classList.remove('premium');
    membershipText.textContent = 'FREE MODE';
  }
}

/* ---------- Input handling ---------- */

function appendNumber(val) {
  if (justCalculated) {
    expression = '';
    currentInput = '0';
    justCalculated = false;
  }
  if (val === '.') {
    if (currentInput.includes('.')) return;
    currentInput = currentInput === '0' || currentInput === ''
      ? '0.'
      : currentInput + '.';
    return;
  }
  currentInput = currentInput === '0' ? val : currentInput + val;
}

function appendOperator(op) {
  if (justCalculated) justCalculated = false;

  if (op === '%') {
    const num = parseFloat(currentInput);
    if (!isNaN(num)) currentInput = String(num / 100);
    updateCurrentDisplay();
    return;
  }

  if (currentInput === '' && expression === '') {
    if (op === '-') { currentInput = '-'; updateCurrentDisplay(); }
    return;
  }

  if (isOperator(expression.slice(-1)) && (currentInput === '' || currentInput === '-')) {
    expression = expression.slice(0, -1) + op;
    updateExpressionDisplay();
    return;
  }

  expression += currentInput + op;
  currentInput = '';
  updateExpressionDisplay();
  resultEl.textContent = '0';
}

/* ---------- WRONG ANSWER GENERATOR (ALWAYS RANDOM) ---------- */

function generateWrongAnswer(correctResult) {
  if (typeof correctResult !== 'number' || !isFinite(correctResult)) {
    return 'Error';
  }
  const isInt = Number.isInteger(correctResult);
  const absCorrect = Math.abs(correctResult);

  const tries = [
    () => {
      const r1 = Math.random();
      const r2 = Math.random();
      const r3 = Math.random();

      let delta;
      if (absCorrect >= 1000000) {
        delta = Math.ceil(absCorrect * (0.03 + r1 * 0.25));
      } else if (absCorrect >= 1000) {
        delta = Math.ceil(absCorrect * (0.05 + r1 * 0.45));
      } else if (absCorrect >= 100) {
        delta = Math.ceil(absCorrect * (0.1 + r1 * 0.6));
      } else if (absCorrect >= 10) {
        delta = Math.ceil(absCorrect * (0.3 + r1 * 1.2));
        if (delta < 5) delta = 5 + Math.floor(r2 * 10);
      } else if (absCorrect >= 1) {
        delta = 2 + Math.floor(r1 * 15);
        if (r2 < 0.5) {
          delta = Math.max(2, Math.ceil(absCorrect * (0.5 + r1 * 3)));
        }
      } else if (absCorrect > 0) {
        delta = 1 + r1 * 3;
      } else {
        delta = 1 + Math.floor(r1 * 9);
      }

      const direction = correctResult >= 0 ? 1 : -1;
      const sign = r3 < 0.5 ? 1 : -1;
      let wrong = correctResult + direction * sign * delta;
      if (isInt) wrong = Math.round(wrong);
      else wrong = Math.round(wrong * 1e4) / 1e4;
      return wrong;
    },
    () => {
      const factor = 0.5 + Math.random() * 2.5;
      const offset = (Math.random() < 0.5 ? -1 : 1) * (1 + Math.floor(Math.random() * 9));
      let wrong;
      if (absCorrect === 0) {
        wrong = offset;
      } else {
        wrong = correctResult * factor + offset;
      }
      if (isInt) wrong = Math.round(wrong);
      else wrong = Math.round(wrong * 1e4) / 1e4;
      return wrong;
    },
    () => {
      let wrong = correctResult + (Math.random() < 0.5 ? -1 : 1) * (1 + Math.floor(Math.random() * 50));
      if (absCorrect >= 10) {
        wrong = correctResult + (Math.random() < 0.5 ? -1 : 1) * Math.ceil(absCorrect * (0.1 + Math.random() * 0.9));
      }
      if (isInt) wrong = Math.round(wrong);
      else wrong = Math.round(wrong * 1e4) / 1e4;
      return wrong;
    },
  ];

  const pickTry = Math.floor(Math.random() * tries.length);
  let wrong = tries[pickTry]();

  let safety = 0;
  while (wrong === correctResult || (absCorrect > 0 && wrong === 0 && Math.random() < 0.7)) {
    safety++;
    if (safety > 20) {
      const forceDelta = absCorrect >= 1 ? Math.max(3, Math.ceil(absCorrect * 0.5)) : 5;
      wrong = correctResult + (correctResult >= 0 ? forceDelta : -forceDelta);
      if (isInt) wrong = Math.round(wrong);
      break;
    }
    const next = Math.floor(Math.random() * tries.length);
    wrong = tries[next]();
  }

  return wrong;
}

/* ---------- Calculate ---------- */

function buildFullExpr() {
  let expr = expression;
  if (isOperator(expr.slice(-1)) && currentInput !== '') {
    expr += currentInput;
  } else if (isOperator(expr.slice(-1))) {
    expr = expr.slice(0, -1);
  } else {
    expr += currentInput;
  }
  return expr;
}

function safeEval(expr) {
  try {
    const val = Function('"use strict"; return (' + expr + ')')();
    return typeof val === 'number' ? val : NaN;
  } catch (e) {
    return NaN;
  }
}

function calculate() {
  if (currentInput === '' && expression === '') return;

  const expr = buildFullExpr();
  if (!expr) return;

  const correctRaw = safeEval(expr);
  const correct = typeof correctRaw === 'number' && isFinite(correctRaw)
    ? Math.round(correctRaw * 1e10) / 1e10
    : NaN;

  const prettyExpr = expr
    .replace(/\*/g, ' × ')
    .replace(/\//g, ' ÷ ')
    .replace(/-/g, ' − ');

  pendingPrettyExpr = prettyExpr;

  const wrong = generateWrongAnswer(correct);
  const displayWrong = wrong === 'Error'
    ? 'Error'
    : formatNumber(String(wrong));

  pendingCorrectResult = isNaN(correct) ? 'Error' : formatNumber(String(correct));
  pendingWrongResult = displayWrong;

  if (isPremium) {
    justCalculated = true;
    showAnswerModal(prettyExpr + ' =', displayWrong);
  } else {
    justCalculated = true;
    openMembershipModal();
    return;
  }
}

/* ---------- Clear / Delete ---------- */

function clearAll() {
  expression = '';
  currentInput = '0';
  justCalculated = false;
  resultEl.style.color = '';
  updateExpressionDisplay();
  updateCurrentDisplay();
}

function deleteLast() {
  if (justCalculated) { clearAll(); return; }
  if (currentInput.length > 0) {
    currentInput = currentInput.slice(0, -1);
    if (currentInput === '') currentInput = '0';
    updateCurrentDisplay();
    return;
  }
  if (expression.length > 0) {
    if (isOperator(expression.slice(-1))) {
      const match = expression.match(/(.*?)([+\-*/])([^+\-*/]*)$/);
      if (match) { expression = match[1]; currentInput = match[3] || '0'; }
      else expression = '';
    } else {
      expression = expression.slice(0, -1);
    }
    updateExpressionDisplay();
    updateCurrentDisplay();
  }
}

/* ---------- Button + keyboard ---------- */

buttons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const value = btn.dataset.value;
    const action = btn.dataset.action;
    resultEl.style.color = '';
    if (action === 'equals') calculate();
    else if (action === 'clear') clearAll();
    else if (action === 'delete') deleteLast();
    else if (value !== undefined) {
      if (isOperator(value)) appendOperator(value);
      else { appendNumber(value); updateCurrentDisplay(); }
    }
  });
});

document.addEventListener('keydown', (e) => {
  const k = e.key;
  resultEl.style.color = '';
  if (/^[0-9]$/.test(k)) { appendNumber(k); updateCurrentDisplay(); }
  else if (k === '.') { appendNumber('.'); updateCurrentDisplay(); }
  else if (k === '+' || k === '-' || k === '*' || k === '/' || k === '%') appendOperator(k);
  else if (k === 'Enter' || k === '=') { e.preventDefault(); calculate(); }
  else if (k === 'Backspace') deleteLast();
  else if (k === 'Escape') clearAll();
});

/* ========== MEMBERSHIP MODAL ========== */

const membershipModal = document.getElementById('membershipModal');
const closeMembershipBtn = document.getElementById('closeMembership');
const planEls = document.querySelectorAll('.plan');
const selectPlanBtns = document.querySelectorAll('.select-plan');
const payNowBtn = document.getElementById('payNowBtn');
const payNowText = document.getElementById('payNowText');

const processingModal = document.getElementById('processingModal');
const processingStep = document.getElementById('processingStep');
const progressFill = document.getElementById('progressFill');

const successModal = document.getElementById('successModal');
const receiptEl = document.getElementById('receipt');
const successSub = document.getElementById('successSub');
const continueBtn = document.getElementById('continueBtn');

const answerModal = document.getElementById('answerModal');
const answerExpressionEl = document.getElementById('answerExpression');
const answerValueEl = document.getElementById('answerValue');
const answerCloseBtn = document.getElementById('answerCloseBtn');

function showAnswerModal(exprDisplay, valueDisplay) {
  answerExpressionEl.textContent = exprDisplay;
  answerValueEl.textContent = valueDisplay;
  answerValueEl.style.animation = 'none';
  void answerValueEl.offsetWidth;
  answerValueEl.style.animation = '';
  answerModal.classList.remove('hidden');
}

function closeAnswerModal() {
  answerModal.classList.add('hidden');
  clearAll();
}

answerCloseBtn.addEventListener('click', closeAnswerModal);
answerModal.addEventListener('click', (e) => {
  if (e.target === answerModal) closeAnswerModal();
});

function updatePayButton() {
  const p = planPrices[selectedPlan];
  payNowText.textContent = `Pay Now — $${p.amount}`;
}

function selectPlan(plan) {
  selectedPlan = plan;
  planEls.forEach((el) => {
    el.classList.toggle('selected', el.dataset.plan === plan);
  });
  updatePayButton();
}

planEls.forEach((el) => {
  el.addEventListener('click', (e) => {
    e.stopPropagation();
    selectPlan(el.dataset.plan);
  });
});

selectPlanBtns.forEach((btn) => {
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    selectPlan(btn.dataset.plan);
  });
});

function openMembershipModal() { membershipModal.classList.remove('hidden'); }
function closeMembershipModal() { membershipModal.classList.add('hidden'); }
closeMembershipBtn.addEventListener('click', closeMembershipModal);
membershipModal.addEventListener('click', (e) => {
  if (e.target === membershipModal) closeMembershipModal();
});

/* ---------- Payment Flow ---------- */

const processingSteps = [
  'Connecting to secure server...',
  'Verifying payment details...',
  'Encrypting transaction...',
  'Charging payment method...',
  'Activating premium license...',
];

payNowBtn.addEventListener('click', () => {
  closeMembershipModal();
  processingModal.classList.remove('hidden');
  progressFill.style.width = '0%';
  processingStep.textContent = processingSteps[0];

  let step = 0;
  const totalSteps = processingSteps.length;
  const stepDuration = 650;

  const interval = setInterval(() => {
    step += 1;
    const progress = Math.min(100, Math.round((step / totalSteps) * 100));
    progressFill.style.width = progress + '%';
    if (step < totalSteps) {
      processingStep.textContent = processingSteps[step];
    } else {
      clearInterval(interval);
      setTimeout(() => {
        processingModal.classList.add('hidden');
        showSuccess();
      }, 350);
    }
  }, stepDuration);
});

function showSuccess() {
  const plan = planPrices[selectedPlan];
  const id = 'CP' + Math.random().toString(36).slice(2, 10).toUpperCase();
  const today = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });

  receiptEl.innerHTML = `
    <div class="receipt-row"><span class="label">Plan</span><span>${plan.label} Pro</span></div>
    <div class="receipt-row"><span class="label">Transaction ID</span><span>${id}</span></div>
    <div class="receipt-row"><span class="label">Date</span><span>${today}</span></div>
    <div class="receipt-row"><span class="label">Payment Method</span><span>Card •••• 4242</span></div>
    <div class="receipt-row"><span class="label">Total</span><span>$${plan.amount}</span></div>
  `;
  successSub.textContent = `${plan.label} plan activated — enjoy correct answers!`;
  successModal.classList.remove('hidden');
  isPremium = true;
  setPremiumBadge();
}

continueBtn.addEventListener('click', () => {
  successModal.classList.add('hidden');
  showAnswerModal(pendingPrettyExpr + ' =', pendingWrongResult);
});

/* ---------- Init ---------- */

setPremiumBadge();
selectPlan('weekly');
updateExpressionDisplay();
updateCurrentDisplay();
