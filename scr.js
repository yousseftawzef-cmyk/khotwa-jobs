const searchForm = document.querySelector("#job-search");
const keywordInput = document.querySelector("#keyword");
const categorySelect = document.querySelector("#category");
const citySelect = document.querySelector("#city");
const jobGrid = document.querySelector("#job-list");
const jobsLoadError = document.querySelector("#jobs-load-error");
let jobCards = [];
let jobsLoaded = false;
const filterButtons = [...document.querySelectorAll(".filter-chip")];
const resultCount = document.querySelector("#results-count");
const emptyState = document.querySelector("#empty-state");
let selectedType = "all";

function normalizeText(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[أإآ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/[\u064B-\u065F\u0670]/g, "");
}

function updateJobs() {
  const keyword = normalizeText(keywordInput.value);
  const category = categorySelect.value;
  const city = citySelect.value;
  let visibleCount = 0;

  jobCards.forEach((card) => {
    const matchesKeyword = normalizeText(card.dataset.search).includes(keyword);
    const matchesCategory = !category || card.dataset.category === category;
    const matchesCity = !city || card.dataset.city === city;
    const matchesType = selectedType === "all" || card.dataset.type === selectedType;
    const isVisible = matchesKeyword && matchesCategory && matchesCity && matchesType;

    card.hidden = !isVisible;
    if (isVisible) visibleCount += 1;
  });

  resultCount.innerHTML = visibleCount
    ? `أحدث الفرص <span>${new Intl.NumberFormat("ar-EG").format(visibleCount)} فرص</span>`
    : "نتائج البحث";
  emptyState.hidden = visibleCount !== 0 || !jobsLoaded;
}

function createTextElement(tagName, className, text) {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  return element;
}

function createJobCard(job) {
  const card = document.createElement("article");
  card.className = "job-card";
  card.dataset.jobId = job.id;
  card.dataset.category = job.category;
  card.dataset.city = job.city;
  card.dataset.type = job.job_type;
  card.dataset.search = `${job.title} ${job.company} ${job.category} ${job.location}`;

  const top = document.createElement("div");
  top.className = "job-card-top";
  top.append(
    createTextElement("span", `company-logo ${job.logo_color}`, job.company_initial),
    createTextElement(
      "span",
      `job-type${job.job_type === "remote" ? " job-type-remote" : ""}${job.job_type === "internship" ? " job-type-training" : ""}`,
      job.job_type_label,
    ),
  );

  const title = createTextElement("h3", "", job.title);
  const company = createTextElement("p", "company-name", job.company);
  const meta = document.createElement("div");
  meta.className = "job-meta";
  meta.append(
    createTextElement("span", "", `⌖ ${job.location}`),
    createTextElement("span", "", `◷ ${job.posted_label}`),
  );

  const bottom = document.createElement("div");
  bottom.className = "job-card-bottom";
  const salary = createTextElement("span", "job-salary", job.salary);
  salary.append(createTextElement("small", "", job.salary_note));
  const applyButton = document.createElement("button");
  applyButton.className = "job-apply";
  applyButton.type = "button";
  applyButton.setAttribute("aria-label", `قدّم على وظيفة ${job.title}`);
  applyButton.append(document.createTextNode("قدّم الآن "));
  applyButton.append(createTextElement("span", "", "←"));
  applyButton.lastElementChild.setAttribute("aria-hidden", "true");
  bottom.append(salary, applyButton);
  card.append(top, title, company, meta, bottom);
  return card;
}

async function loadJobs() {
  try {
    const response = await fetch("/api/jobs", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`تعذر تحميل الوظائف (${response.status}).`);

    const data = await response.json();
    if (!Array.isArray(data.jobs)) throw new Error("استجابة الوظائف غير صالحة.");

    jobCards = data.jobs.map(createJobCard);
    jobGrid.replaceChildren(...jobCards);
    jobGrid.setAttribute("aria-busy", "false");
    jobsLoaded = true;
    jobsLoadError.hidden = true;
    updateJobs();
  } catch (error) {
    console.error("Failed to load job listings.", error);
    jobGrid.replaceChildren();
    jobGrid.setAttribute("aria-busy", "false");
    resultCount.textContent = "تعذر تحميل الوظائف";
    jobsLoadError.hidden = false;
  }
}

async function loadStats() {
  const statisticElements = document.querySelectorAll("[data-stat]");

  try {
    const response = await fetch("/api/stats", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`تعذر تحميل الإحصائيات (${response.status}).`);

    const stats = await response.json();
    statisticElements.forEach((element) => {
      const value = stats[element.dataset.stat];
      if (!Number.isInteger(value)) throw new Error("استجابة الإحصائيات غير صالحة.");
      element.textContent = `+${new Intl.NumberFormat("ar-EG").format(value)}`;
    });
  } catch (error) {
    console.error("Failed to load platform statistics.", error);
    statisticElements.forEach((element) => {
      element.textContent = "—";
    });
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  updateJobs();
});

keywordInput.addEventListener("input", updateJobs);
categorySelect.addEventListener("change", updateJobs);
citySelect.addEventListener("change", updateJobs);

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    selectedType = button.dataset.filter;
    filterButtons.forEach((filter) => {
      const isSelected = filter === button;
      filter.classList.toggle("selected", isSelected);
      filter.setAttribute("aria-pressed", String(isSelected));
    });
    updateJobs();
  });
  button.setAttribute("aria-pressed", String(button.classList.contains("selected")));
});

const menuToggle = document.querySelector(".menu-toggle");
const mainNav = document.querySelector("#main-nav");

menuToggle.addEventListener("click", () => {
  const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
  menuToggle.setAttribute("aria-expanded", String(!isExpanded));
  menuToggle.setAttribute("aria-label", isExpanded ? "فتح القائمة" : "إغلاق القائمة");
  mainNav.classList.toggle("is-open", !isExpanded);
});

mainNav.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    menuToggle.setAttribute("aria-expanded", "false");
    menuToggle.setAttribute("aria-label", "فتح القائمة");
    mainNav.classList.remove("is-open");
  });
});

document.querySelector("#newsletter-form").addEventListener("submit", (event) => {
  event.preventDefault();
  document.querySelector("#newsletter-feedback").textContent =
    "الاشتراك بالبريد غير متاح في النسخة التجريبية.";
});

const applicationDialog = document.querySelector("#application-dialog");
const applicationForm = document.querySelector("#application-form");
const applicationError = document.querySelector("#application-error");
const applicationSuccess = document.querySelector("#application-success");
const applicationActions = document.querySelector("#application-actions");
const applicantCv = document.querySelector("#applicant-cv");
const applicantPhone = document.querySelector("#applicant-phone");
const accountDialog = document.querySelector("#account-dialog");
const accountForm = document.querySelector("#account-form");
const accountError = document.querySelector("#account-error");
const dashboardDialog = document.querySelector("#dashboard-dialog");
const dashboardError = document.querySelector("#dashboard-error");
const postJobDialog = document.querySelector("#post-job-dialog");
const postJobForm = document.querySelector("#post-job-form");
const postJobError = document.querySelector("#post-job-error");
const accountOpenButton = document.querySelector("#account-open-button");
const accountDashboardButton = document.querySelector("#account-dashboard-button");
const maxCvSize = 5 * 1024 * 1024;
const allowedCvExtensions = /\.(pdf|docx?)$/i;

let selectedJobId = null;
let currentAccount = null;
let csrfToken = "";
let accountMode = "login";
let authReady = Promise.resolve();

async function requestJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.method && options.method !== "GET") {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(url, { ...options, headers });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("تعذر معالجة استجابة الخادم. حاول مرة أخرى لاحقًا.");
  }
  if (!response.ok) throw new Error(data.error || "تعذر تنفيذ الطلب.");
  return data;
}

function updateAccountButtons() {
  accountOpenButton.hidden = Boolean(currentAccount);
  accountDashboardButton.hidden = !currentAccount;
  if (currentAccount) {
    accountDashboardButton.textContent =
      currentAccount.role === "employer" ? currentAccount.company_name : currentAccount.name;
  }
}

async function loadAuthSession() {
  try {
    const data = await requestJson("/api/auth/session");
    csrfToken = data.csrf_token;
    currentAccount = data.account;
    updateAccountButtons();
  } catch (error) {
    console.error("Failed to load the account session.", error);
    accountOpenButton.disabled = true;
    accountOpenButton.textContent = "تعذر الاتصال";
  }
}

function setFieldVisible(field, visible, required = false) {
  field.hidden = !visible;
  const input = field.querySelector("input, select");
  if (input) input.required = visible && required;
}

function updateAccountForm() {
  const isRegister = accountMode === "register";
  const role = document.querySelector("#account-role").value;
  accountForm.querySelectorAll(".account-register-field").forEach((field) => {
    setFieldVisible(field, isRegister);
  });
  accountForm.querySelectorAll(".account-seeker-field").forEach((field) => {
    const required = !field.querySelector('input[type="file"]');
    setFieldVisible(field, isRegister && role === "seeker", required);
  });
  accountForm.querySelectorAll(".account-employer-field").forEach((field) => {
    setFieldVisible(field, isRegister && role === "employer", field.id === "company-name");
  });
  accountForm.querySelector("#account-name").required = isRegister;
  accountForm.querySelector("#account-phone").required = isRegister;
  accountForm.querySelector("#account-role").required = isRegister;
  accountForm.querySelector('[name="account_consent"]').required = isRegister;
  document.querySelector("#account-dialog-title").textContent =
    isRegister ? "إنشاء حساب جديد" : "دخول الحساب";
  document.querySelector("#account-submit").innerHTML = isRegister
    ? 'إنشاء الحساب <span aria-hidden="true">←</span>'
    : 'تسجيل الدخول <span aria-hidden="true">←</span>';
  document.querySelector("#account-password").autocomplete = isRegister
    ? "new-password"
    : "current-password";
  accountForm.querySelectorAll("[data-account-mode]").forEach((button) => {
    const isSelected = button.dataset.accountMode === accountMode;
    button.classList.toggle("selected", isSelected);
    button.setAttribute("aria-pressed", String(isSelected));
  });
}

function openAccountDialog(mode = "login") {
  accountMode = mode;
  accountForm.reset();
  document.querySelector("#account-phone").setCustomValidity("");
  accountError.hidden = true;
  updateAccountForm();
  if (!accountDialog.open) accountDialog.showModal();
}

async function showDashboard() {
  if (!currentAccount) {
    openAccountDialog("login");
    return;
  }

  dashboardError.hidden = true;
  document.querySelector("#dashboard-title").textContent =
    currentAccount.role === "employer" ? currentAccount.company_name : "حساب الباحث عن عمل";
  document.querySelector("#dashboard-subtitle").textContent =
    `${currentAccount.name} · ${currentAccount.email}`;
  document.querySelector("#seeker-dashboard").hidden = currentAccount.role !== "seeker";
  document.querySelector("#employer-dashboard").hidden = currentAccount.role !== "employer";

  if (currentAccount.role === "seeker") {
    const profileSummary = document.querySelector("#seeker-profile-summary");
    profileSummary.replaceChildren(
      createTextElement("strong", "", currentAccount.name),
      createTextElement("span", "", currentAccount.specialization),
      createTextElement("span", "", currentAccount.city === "remote" ? "عن بُعد" : currentAccount.city),
      createTextElement("span", "", currentAccount.phone),
    );
    document.querySelector("#profile-cv-button").hidden = !currentAccount.has_cv;
  } else {
    await loadEmployerDashboard();
  }

  dashboardDialog.showModal();
}

async function loadEmployerDashboard() {
  const jobsList = document.querySelector("#employer-jobs-list");
  const applicationsList = document.querySelector("#employer-applications-list");
  jobsList.replaceChildren();
  applicationsList.replaceChildren();

  try {
    const [jobs, applications] = await Promise.all([
      requestJson("/api/employer/jobs"),
      requestJson("/api/employer/applications"),
    ]);

    if (!jobs.jobs.length) {
      jobsList.append(createTextElement("p", "dashboard-empty", "لسه ما نشرتش وظائف."));
    }
    jobs.jobs.forEach((job) => {
      const item = document.createElement("article");
      item.className = "dashboard-item";
      item.append(
        createTextElement("strong", "", job.title),
        createTextElement("span", "", `${job.location} · ${job.job_type_label}`),
        createTextElement(
          "span",
          "dashboard-item-count",
          `${new Intl.NumberFormat("ar-EG").format(job.applications_count)} طلبات`,
        ),
      );
      jobsList.append(item);
    });

    if (!applications.applications.length) {
      applicationsList.append(
        createTextElement("p", "dashboard-empty", "لا توجد طلبات تقديم على وظائفك حتى الآن."),
      );
    }
    applications.applications.forEach((application) => {
      const item = document.createElement("article");
      item.className = "dashboard-item";
      item.append(
        createTextElement("strong", "", application.applicant_name),
        createTextElement("span", "", application.job_title),
        createTextElement("span", "", `${application.email} · ${application.phone}`),
      );
      if (application.has_cv) {
        const resumeLink = document.createElement("a");
        resumeLink.className = "dashboard-resume-link";
        resumeLink.href = `/api/employer/applications/${application.id}/cv`;
        resumeLink.textContent = "تحميل السيرة الذاتية";
        item.append(resumeLink);
      }
      applicationsList.append(item);
    });
  } catch (error) {
    console.error("Failed to load the employer dashboard.", error);
    dashboardError.textContent = error.message;
    dashboardError.hidden = false;
  }
}

function openApplicationForJob(jobCard) {
  selectedJobId = jobCard.dataset.jobId;
  applicationForm.reset();
  applicantPhone.setCustomValidity("");
  applicationError.hidden = true;
  applicationSuccess.hidden = true;
  applicationActions.hidden = false;
  applicationForm.querySelectorAll(".form-field, .application-form-field").forEach((field) => {
    field.hidden = false;
  });
  document.querySelector("#applicant-name").value = currentAccount.name;
  document.querySelector("#applicant-email").value = currentAccount.email;
  document.querySelector("#applicant-phone").value = currentAccount.phone;
  document.querySelector("#applicant-name").readOnly = true;
  document.querySelector("#applicant-email").readOnly = true;
  document.querySelector("#applicant-phone").readOnly = true;
  document.querySelector("#application-privacy-note").textContent = currentAccount.has_cv
    ? "سيرتك المحفوظة بحسابك ستُرفق تلقائيًا إذا لم تختر ملفًا آخر."
    : "سيتم مشاركة بياناتك مع الشركة المعلنة لمراجعة الطلب.";
  document.querySelector("#dialog-job-title").textContent =
    `${jobCard.querySelector("h3").textContent} — ${jobCard.querySelector(".company-name").textContent}`;
  applicationSuccess.querySelector("p").textContent =
    "تم حفظ طلبك، وسيتم التواصل معك عند مراجعة بياناتك.";
  if (!applicationDialog.open) applicationDialog.showModal();
}

jobGrid.addEventListener("click", async (event) => {
  const button = event.target.closest(".job-apply");
  if (!button) return;

  await authReady;
  const jobCard = button.closest(".job-card");
  if (!currentAccount) {
    selectedJobId = jobCard.dataset.jobId;
    openAccountDialog("login");
    accountError.textContent = "سجّل الدخول أو أنشئ حساب باحث عن عمل للتقديم.";
    accountError.hidden = false;
    return;
  }
  if (currentAccount.role !== "seeker") {
    dashboardError.textContent = "التقديم على الوظائف متاح لحسابات الباحثين عن عمل فقط.";
    dashboardError.hidden = false;
    dashboardDialog.showModal();
    return;
  }
  openApplicationForJob(jobCard);
});

function closeApplicationDialog() {
  applicationDialog.close();
}

document.querySelector(".dialog-close").addEventListener("click", closeApplicationDialog);
document.querySelector(".cancel-application").addEventListener("click", closeApplicationDialog);

applicantPhone.addEventListener("input", () => {
  const isValidPhone = /^(?=.*[0-9٠-٩])[0-9٠-٩+() -]{8,20}$/.test(applicantPhone.value);
  applicantPhone.setCustomValidity(isValidPhone ? "" : "اكتب رقم تلفون صحيحًا.");
});

document.querySelector("#account-phone").addEventListener("input", (event) => {
  const isValidPhone = /^(?=.*[0-9٠-٩])[0-9٠-٩+() -]{8,20}$/.test(event.target.value);
  event.target.setCustomValidity(isValidPhone ? "" : "اكتب رقم تلفون صحيحًا.");
});

accountOpenButton.addEventListener("click", async () => {
  await authReady;
  openAccountDialog("login");
});
accountDashboardButton.addEventListener("click", async () => {
  await authReady;
  await showDashboard();
});
document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    document.getElementById(button.dataset.closeDialog).close();
  });
});
document.querySelectorAll("[data-account-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    accountMode = button.dataset.accountMode;
    accountError.hidden = true;
    updateAccountForm();
  });
});
document.querySelector("#account-role").addEventListener("change", updateAccountForm);
document.querySelector("#dashboard-post-button").addEventListener("click", () => {
  postJobForm.reset();
  postJobError.hidden = true;
  postJobDialog.showModal();
});
document.querySelector("#profile-cv-button").addEventListener("click", () => {
  window.location.assign("/api/profile/cv");
});
document.querySelector("#logout-button").addEventListener("click", async () => {
  const logoutButton = document.querySelector("#logout-button");
  logoutButton.disabled = true;
  try {
    const result = await requestJson("/api/auth/logout", { method: "POST" });
    csrfToken = result.csrf_token;
    currentAccount = null;
    selectedJobId = null;
    updateAccountButtons();
    dashboardDialog.close();
  } catch (error) {
    console.error("Failed to log out.", error);
    dashboardError.textContent = error.message;
    dashboardError.hidden = false;
  } finally {
    logoutButton.disabled = false;
  }
});

accountForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  accountError.hidden = true;
  const submitButton = document.querySelector("#account-submit");
  const register = accountMode === "register";
  const role = document.querySelector("#account-role").value;
  if (register && document.querySelector('[name="account_consent"]').checked === false) {
    accountError.textContent = "وافق على حفظ بياناتك لإنشاء الحساب.";
    accountError.hidden = false;
    return;
  }

  submitButton.disabled = true;
  try {
    const formData = new FormData(accountForm);
    const result = await requestJson(
      register ? "/api/auth/register" : "/api/auth/login",
      { method: "POST", body: formData },
    );
    currentAccount = result.account;
    csrfToken = result.csrf_token;
    updateAccountButtons();
    accountDialog.close();

    if (selectedJobId && currentAccount.role === "seeker") {
      const selectedCard = jobCards.find((card) => card.dataset.jobId === selectedJobId);
      if (selectedCard) openApplicationForJob(selectedCard);
      return;
    }

    if (selectedJobId && currentAccount.role === "employer") {
      selectedJobId = null;
      await showDashboard();
      dashboardError.textContent = "التقديم على الوظائف متاح لحسابات الباحثين عن عمل فقط.";
      dashboardError.hidden = false;
      return;
    }

    if (role === "employer" || currentAccount.role === "employer") {
      await showDashboard();
    }
  } catch (error) {
    console.error("Account request failed.", error);
    accountError.textContent =
      error instanceof TypeError
        ? "تعذر الاتصال بالخادم. حاول مرة أخرى."
        : error.message;
    accountError.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});

postJobForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  postJobError.hidden = true;
  const submitButton = postJobForm.querySelector('[type="submit"]');
  submitButton.disabled = true;

  try {
    const result = await requestJson("/api/employer/jobs", {
      method: "POST",
      body: new FormData(postJobForm),
    });
    postJobDialog.close();
    await Promise.all([loadJobs(), loadStats()]);
    await loadEmployerDashboard();
    dashboardError.textContent = result.message;
    dashboardError.hidden = false;
  } catch (error) {
    console.error("Failed to publish a job.", error);
    postJobError.textContent = error.message;
    postJobError.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});

applicationDialog.addEventListener("click", (event) => {
  if (event.target === applicationDialog) closeApplicationDialog();
});

applicationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const cv = applicantCv.files[0];

  if (cv && !allowedCvExtensions.test(cv.name)) {
    applicationError.textContent = "ارفع السيرة الذاتية بصيغة PDF أو Word.";
    applicationError.hidden = false;
    applicantCv.focus();
    return;
  }

  if (cv && cv.size > maxCvSize) {
    applicationError.textContent = "حجم السيرة الذاتية يجب ألا يتجاوز ٥ ميجابايت.";
    applicationError.hidden = false;
    applicantCv.focus();
    return;
  }

  applicationError.hidden = true;
  const submitButton = applicationForm.querySelector('[type="submit"]');
  submitButton.disabled = true;

  try {
    const formData = new FormData(applicationForm);
    formData.set("job_id", selectedJobId);
    const result = await requestJson("/api/applications", {
      method: "POST",
      body: formData,
    });

    applicationSuccess.querySelector("p").textContent = result.message;
    applicationForm.querySelectorAll(".form-field, .application-form-field").forEach((field) => {
      field.hidden = true;
    });
    applicationActions.hidden = true;
    applicationSuccess.hidden = false;
    await loadStats();
  } catch (error) {
    console.error("Failed to submit job application.", error);
    applicationError.textContent =
      error instanceof TypeError
        ? "تعذر الاتصال بالخادم. تأكد من تشغيل الموقع من خلال التطبيق."
        : error.message;
    applicationError.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});

loadJobs();
loadStats();
authReady = loadAuthSession().then(() => {
  updateAccountForm();
});