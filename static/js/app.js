// ============================================
// 多模态智能反诈对话系统 v2.0 - 前端主逻辑
// 游戏化交互 + 智能研判 + 多功能模态
// ============================================

class AntiFraudApp {
  constructor() {
    this.userId = document.getElementById('app-data')?.dataset?.userId || 'anonymous';
    this.conversationId = this.generateId();
    this.scenarioState = null;
    this.scenarioScore = 0;
    this.isRecording = false;
    this.recognition = null;
    this.userPoints = 0;
    this.userLevel = null;
    this._isSending = false;

    this.init();
  }

  generateId() {
    return Math.random().toString(36).substring(2, 10);
  }

  init() {
    this.setupElements();
    this.setupEventListeners();
    this.setupSpeechRecognition();
    this.showEmptyState();
    this.loadUserProfile();
    this.loadDailyTasks();
    this.loadPrivacyStatus();
    // 暗色模式
    this.initTheme();
    // 加载欢迎语 - 使用isAuto=true避免空消息被拦截
    this.sendMessage({ message: '', isAuto: true });
    // 加载历史对话记忆（隐私安全版）
    this.loadHistoryMemory();
    // 注册页面关闭时清除隐私数据
    this.setupPrivacyCleanup();
    // 监听窗口大小变化，调整布局
    window.addEventListener('resize', () => this.scrollToBottom());
  }

  // 加载历史对话记忆
  async loadHistoryMemory() {
    try {
      const res = await fetch(`/api/history/memory?user_id=${this.userId}`);
      const data = await res.json();
      if (data.has_history && data.history.length > 1) {
        // 添加一个记忆分隔条
        const memoryDiv = document.createElement('div');
        memoryDiv.className = 'memory-divider';
        memoryDiv.innerHTML = '<span>📜 上次的对话记录</span>';
        this.elements.chatMessages.appendChild(memoryDiv);

        // 加载历史消息（隐私信息已脱敏）
        for (const msg of data.history) {
          if (msg.role === 'user') {
            this.addMessage(msg.content, 'user');
          } else if (msg.role === 'assistant') {
            this.addMessage(msg.content, 'bot', { type: msg.msg_type });
          }
        }

        const continueDiv = document.createElement('div');
        continueDiv.className = 'memory-divider';
        continueDiv.innerHTML = '<span>💬 继续对话</span>';
        this.elements.chatMessages.appendChild(continueDiv);
      }
    } catch (e) {
      console.warn('加载对话记忆失败:', e.message);
    }
  }

  // 页面关闭时自动清除隐私数据
  setupPrivacyCleanup() {
    const clearPrivacy = () => {
      try {
        navigator.sendBeacon('/api/privacy/clear-session',
          new Blob([JSON.stringify({ user_id: this.userId })], { type: 'application/json' }));
      } catch (e) { /* ignore */ }
    };
    window.addEventListener('beforeunload', clearPrivacy);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        clearPrivacy();
      }
    });
  }

  // 加载隐私保护状态
  async loadPrivacyStatus() {
    try {
      const res = await fetch(`/api/privacy/status?user_id=${this.userId}`);
      const data = await res.json();
      if (data.protected > 0) {
        this.showToast(`🔒 隐私卫士已保护 ${data.protected} 条个人信息`);
        this.updatePrivacyStatus(data.protected);
      }
    } catch (e) { /* ignore */ }
  }

  // 更新侧边栏隐私状态显示
  updatePrivacyStatus(protectedCount) {
    const sidebarStatus = document.getElementById('privacy-status-sidebar');
    const privacyCount = document.getElementById('privacy-count');
    if (sidebarStatus) {
      sidebarStatus.style.display = 'block';
    }
    if (privacyCount) {
      privacyCount.textContent = `已保护 ${protectedCount} 条`;
    }
  }

  setupElements() {
    this.elements = {
      chatMessages: document.getElementById('chat-messages'),
      userInput: document.getElementById('user-input'),
      sendBtn: document.getElementById('send-btn'),
      voiceBtn: document.getElementById('voice-btn'),
      sidebar: document.getElementById('sidebar'),
      menuToggle: document.getElementById('menu-toggle'),
      profileArea: document.getElementById('profile-area'),
      badgesContainer: document.getElementById('badges-container'),
      streakDisplay: document.getElementById('streak-display'),
      streakCount: document.getElementById('streak-count'),
      dailyTasksArea: document.getElementById('daily-tasks-area'),
      suggestionArea: document.getElementById('suggestion-area'),

      // Modals
      scenarioModal: document.getElementById('scenario-modal'),
      scenarioList: document.getElementById('scenario-list'),
      scenarioScene: document.getElementById('scenario-scene'),
      reportModal: document.getElementById('report-modal'),
      reportUrlInput: document.getElementById('report-url'),
      reportDescInput: document.getElementById('report-desc'),
      reportBtn: document.getElementById('report-btn'),
      reportResult: document.getElementById('report-result'),
      reportHistory: document.getElementById('report-history'),
      knowledgeModal: document.getElementById('knowledge-modal'),
      knowledgeContent: document.getElementById('knowledge-content'),
      leaderboardModal: document.getElementById('leaderboard-modal'),
      leaderboardContent: document.getElementById('leaderboard-content'),
      historyModal: document.getElementById('history-modal'),
      historyList: document.getElementById('history-list'),
      historyRefreshBtn: document.getElementById('history-refresh-btn'),
      historyLoadLatestBtn: document.getElementById('history-load-latest-btn'),
    };
  }

  setupEventListeners() {
    this.elements.sendBtn.addEventListener('click', () => this.handleSend());
    this.elements.userInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSend();
      }
    });
    this.elements.userInput.addEventListener('input', () => {
      this.elements.userInput.style.height = 'auto';
      this.elements.userInput.style.height = Math.min(this.elements.userInput.scrollHeight, 120) + 'px';
    });
    this.elements.voiceBtn.addEventListener('click', () => this.toggleVoice());
    this.elements.menuToggle.addEventListener('click', () => this.toggleSidebar());

    document.querySelectorAll('.nav-item[data-action]').forEach(item => {
      item.addEventListener('click', () => {
        const action = item.dataset.action;
        this.handleNavAction(action);
        if (window.innerWidth <= 768) this.toggleSidebar();
      });
    });

    this.elements.reportBtn.addEventListener('click', () => this.handleReport());

    // 历史对话按钮
    if (this.elements.historyRefreshBtn) {
      this.elements.historyRefreshBtn.addEventListener('click', () => this.loadHistoryList());
    }
    if (this.elements.historyLoadLatestBtn) {
      this.elements.historyLoadLatestBtn.addEventListener('click', () => this.loadHistoryToChat());
    }

    document.querySelectorAll('.modal-close').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
      });
    });
    document.querySelectorAll('.modal-overlay').forEach(m => {
      m.addEventListener('click', (e) => {
        if (e.target === m) m.classList.remove('active');
      });
    });
  }

  setupSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.lang = 'zh-CN';
      this.recognition.continuous = false;
      this.recognition.interimResults = false;

      this.recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        this.elements.userInput.value = text;
        this.handleSend();
        this.stopVoice();
      };
      this.recognition.onerror = () => {
        this.stopVoice();
        this.showToast('语音识别失败，请重试');
      };
      this.recognition.onend = () => this.stopVoice();
    }
  }

  toggleVoice() {
    if (!this.recognition) {
      this.showToast('您的浏览器不支持语音识别，请使用Chrome浏览器');
      return;
    }
    this.isRecording ? this.stopVoice() : this.startVoice();
  }

  startVoice() {
    try {
      this.recognition.start();
      this.isRecording = true;
      this.elements.voiceBtn.classList.add('recording');
      this.elements.voiceBtn.textContent = '🎤';
      this.showToast('🎤 正在聆听...');
    } catch (e) { /* ignore */ }
  }

  stopVoice() {
    try { this.recognition.stop(); } catch (e) { /* ignore */ }
    this.isRecording = false;
    this.elements.voiceBtn.classList.remove('recording');
    this.elements.voiceBtn.textContent = '🎙️';
  }

  toggleSidebar() {
    this.elements.sidebar.classList.toggle('open');
  }

  handleNavAction(action) {
    switch (action) {
      case 'scenario': this.openScenarioList(); break;
      case 'report': this.openReportModal(); break;
      case 'knowledge': this.openKnowledgeBase(); break;
      case 'leaderboard': this.openLeaderboard(); break;
      case 'history': this.openHistory(); break;
      case 'privacy': this.showPrivacyStatus(); break;
      case 'clear': this.clearChat(); break;
      case 'help': this.sendMessage({ message: '帮助' }); break;
      // v3.0 智能分析
      case 'smart-analyze': this.showSmartAnalyze(); break;
      case 'image-detect': this.showImageDetect(); break;
      case 'audio-detect': this.showAudioDetect(); break;
    }
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector(`.nav-item[data-action="${action}"]`)?.classList.add('active');
  }

  // 显示隐私保护状态
  async showPrivacyStatus() {
    try {
      const res = await fetch(`/api/privacy/status?user_id=${this.userId}`);
      const data = await res.json();

      let message = '🔒 **隐私保护报告**\n\n';
      message += `**当前会话受保护信息：** ${data.protected || 0} 条\n`;

      if (data.type_names && data.type_names.length > 0) {
        message += '\n**已检测并加密的隐私类型：**\n';
        data.type_names.forEach(t => { message += `• ${t}\n`; });
      } else {
        message += '\n✅ 目前没有检测到个人信息泄露。继续保持！\n';
      }

      if (data.database_protected > 0) {
        message += `\n📊 历史累计保护隐私记录：${data.database_protected} 条\n`;
      }

      message += '\n**隐私保护机制：**\n';
      message += '• 🔐 检测到个人信息自动加密，后台人员也无法查看\n';
      message += '• ⚠️ 发现隐私泄露时自动提醒您\n';
      message += '• 🧹 关闭对话后自动清除隐私数据\n';
      message += '• 📜 下次对话可查看历史（隐私信息已脱敏）\n\n';
      message += '📞 如怀疑个人信息已被诈骗分子获取，请立即拨打 **110** 报警！';

      this.addMessage(message, 'bot', { type: 'privacy_report' });
    } catch (e) {
      this.showToast('加载隐私状态失败');
    }
  }

  async handleSend() {
    const text = this.elements.userInput.value.trim();
    if (!text) return;
    if (this._isSending) return; // 防止重复提交
    this.elements.userInput.value = '';
    this.elements.userInput.style.height = 'auto';
    this.elements.suggestionArea.innerHTML = '';
    this.sendMessage({ message: text });
  }

  async sendMessage(data) {
    const { message, isAuto } = data;

    // 如果是空消息且不是自动发送，直接忽略
    if (!message && !isAuto) return;
    if (this._isSending && !isAuto) return;

    // 移除空状态（如果有）
    this.hideEmptyState();

    // 用户消息不为空时才添加到聊天区域
    if (message) {
      this.addMessage(message, 'user');
    }

    this._isSending = true;
    this.showTyping();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s 超时

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message || '__init__', user_id: this.userId }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      // 检查HTTP状态
      if (!response.ok) {
        throw new Error(`服务器错误 (${response.status})`);
      }

      const result = await response.json();
      this.hideTyping();
      this._isSending = false;

      if (!result || typeof result !== 'object') {
        throw new Error('服务器返回格式异常');
      }

      let fullResponse = result.response || '抱歉，我现在无法回答这个问题。请尝试其他问题。';

      if (result.intervention) {
        fullResponse += '\n\n' + result.intervention;
      }
      if (result.url_warning) {
        fullResponse += '\n\n' + result.url_warning;
      }

      this.addMessage(fullResponse, 'bot', {
        type: result.type,
        riskLevel: result.risk_level,
        extraData: result.extra_data,
        riskDetails: result.risk_details
      });

      // 显示快捷建议
      if (result.suggestions && result.suggestions.length > 0) {
        this.showSuggestions(result.suggestions);
      }

      if (result.type === 'scenario_list' && result.extra_data?.scenarios) {
        this.showScenarioCards(result.extra_data.scenarios);
      }

      // 更新隐私状态
      if (result.privacy_protected !== undefined || result.has_privacy_alert) {
        this.updatePrivacyStatus(result.privacy_protected || 0);
      }

      // 非关键请求不阻塞主流程
      this.loadUserProfile();
      this.loadDailyTasks();
      this.scrollToBottom();

    } catch (error) {
      this.hideTyping();
      this._isSending = false;

      if (error.name === 'AbortError') {
        this.addMessage('⏱️ 请求超时，请检查网络后重试。', 'bot');
      } else {
        this.addMessage('😓 抱歉，网络出现错误，请稍后再试。', 'bot');
      }
      console.warn('Chat API error:', error.message);
    }
  }

  addMessage(text, role, options = {}) {
    // 确保聊天区域有正确的高度
    this.ensureChatAreaVisible();

    const div = document.createElement('div');
    div.className = `message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = role === 'user' ? '你' : '🤖 反诈助手';
    bubble.appendChild(label);

    const content = document.createElement('div');
    content.innerHTML = this.formatMessage(text || '');
    bubble.appendChild(content);

    // 风险警告 + 一键操作按钮
    if (options.riskLevel === 'critical' || options.riskLevel === 'high') {
      const alertDiv = document.createElement('div');
      alertDiv.className = `risk-alert ${options.riskLevel}`;
      const riskIcon = options.riskLevel === 'critical' ? '🚨' : '⚠️';
      const riskText = options.riskLevel === 'critical'
        ? '🆘 高危机警！请立即采取行动！'
        : '⚠️ 存在明显诈骗特征，请提高警惕！';
      alertDiv.innerHTML = `<strong>${riskIcon} ${riskText}</strong>`;

      // 添加风险详情
      if (options.riskDetails?.triggered_categories?.length) {
        const detailEl = document.createElement('div');
        detailEl.style.marginTop = '8px';
        detailEl.style.fontSize = '12px';
        detailEl.textContent = '触发: ' + options.riskDetails.triggered_categories.join('、');
        alertDiv.appendChild(detailEl);
      }
      bubble.appendChild(alertDiv);

      // === 一键快捷操作按钮（高风险时显示） ===
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'bubble-actions';
      actionsDiv.style.cssText = 'display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px;';

      // 一键报警按钮
      const alarmBtn = document.createElement('button');
      alarmBtn.className = 'action-btn action-btn-danger';
      alarmBtn.innerHTML = '🚨 立即报警 110';
      alarmBtn.onclick = () => window.open('tel:110', '_self');
      actionsDiv.appendChild(alarmBtn);

      // 反诈专线
      const hotlineBtn = document.createElement('button');
      hotlineBtn.className = 'action-btn action-btn-warning';
      hotlineBtn.innerHTML = '📞 反诈专线 96110';
      hotlineBtn.onclick = () => window.open('tel:96110', '_self');
      actionsDiv.appendChild(hotlineBtn);

      // 举报该内容
      const reportActionBtn = document.createElement('button');
      reportActionBtn.className = 'action-btn action-btn-primary';
      reportActionBtn.innerHTML = '📢 一键举报';
      reportActionBtn.onclick = () => this.quickReportFromChat(text);
      actionsDiv.appendChild(reportActionBtn);

      bubble.appendChild(actionsDiv);
    }

    // 检测消息中是否包含链接 → 添加举报按钮
    const urlMatch = text.match(/https?:\/\/[^\s<>"\'，。；；！？、\n]+/);
    if (urlMatch && options.riskLevel !== 'critical' && options.riskLevel !== 'high') {
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'bubble-actions';
      actionsDiv.style.cssText = 'display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px;';

      const reportLinkBtn = document.createElement('button');
      reportLinkBtn.className = 'action-btn action-btn-primary';
      reportLinkBtn.innerHTML = '🔍 分析该链接';
      reportLinkBtn.onclick = () => this.quickAnalyzeUrl(urlMatch[0]);
      actionsDiv.appendChild(reportLinkBtn);

      const reportSubmitBtn = document.createElement('button');
      reportSubmitBtn.className = 'action-btn action-btn-warning';
      reportSubmitBtn.innerHTML = '📢 举报此链接';
      reportSubmitBtn.onclick = () => this.quickReportUrl(urlMatch[0]);
      actionsDiv.appendChild(reportSubmitBtn);

      bubble.appendChild(actionsDiv);
    }

    // URL报告类型添加额外操作
    if (options.type === 'url_report' && options.extraData?.url_analysis) {
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'bubble-actions';
      actionsDiv.style.cssText = 'display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px;';

      const submitReportBtn = document.createElement('button');
      submitReportBtn.className = 'action-btn action-btn-danger';
      submitReportBtn.innerHTML = '📢 提交正式举报';
      submitReportBtn.onclick = async () => {
        try {
          await fetch('/api/report/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: this.userId })
          });
          this.showToast('✅ 举报已提交！建议同步拨打96110');
        } catch (e) {
          this.showToast('提交失败，请直接拨打96110');
        }
      };
      actionsDiv.appendChild(submitReportBtn);

      const saveEvidenceBtn = document.createElement('button');
      saveEvidenceBtn.className = 'action-btn action-btn-primary';
      saveEvidenceBtn.innerHTML = '💾 保存证据指引';
      saveEvidenceBtn.onclick = () => {
        this.sendMessage({ message: '被骗后证据怎么保存' });
      };
      actionsDiv.appendChild(saveEvidenceBtn);

      bubble.appendChild(actionsDiv);
    }

    // 添加"举报该内容"按钮到普通机器人消息末尾
    if (role === 'bot' && !options.type?.startsWith('url_') && options.type !== 'greeting' && options.riskLevel !== 'critical' && options.riskLevel !== 'high') {
      const reportThisBtn = document.createElement('div');
      reportThisBtn.style.cssText = 'margin-top: 10px; font-size: 12px; color: var(--text-secondary); cursor: pointer; user-select: none;';
      reportThisBtn.innerHTML = '📢 内容不准确或需要举报？<span style="color: var(--primary); text-decoration: underline;">点击反馈</span>';
      reportThisBtn.onclick = () => {
        this.elements.userInput.value = '我要举报可疑信息';
        this.handleSend();
      };
      bubble.appendChild(reportThisBtn);
    }

    div.appendChild(bubble);
    this.elements.chatMessages.appendChild(div);
    this.scrollToBottom();
  }

  // === 快捷操作：从对话中一键举报 ===
  quickReportFromChat(contextText) {
    this.elements.reportUrlInput.value = '';
    this.elements.reportDescInput.value = contextText.substring(0, 200);
    this.elements.reportModal.classList.add('active');
    this.loadReportHistory();
    this.showToast('📢 请填写要举报的链接');
  }

  // === 快捷分析链接 ===
  async quickAnalyzeUrl(url) {
    this.showToast('🔍 正在分析链接...');
    this.elements.userInput.value = url;
    this.handleSend();
  }

  // === 快捷举报链接 ===
  quickReportUrl(url) {
    this.elements.reportUrlInput.value = url;
    this.elements.reportDescInput.value = '';
    this.elements.reportModal.classList.add('active');
    this.loadReportHistory();
  }

  // 确保聊天消息区域可见（防止flex布局塌陷）
  ensureChatAreaVisible() {
    const container = this.elements.chatMessages;
    if (container) {
      container.style.minHeight = '100px';
    }
  }

  // 显示空状态
  showEmptyState() {
    const container = this.elements.chatMessages;
    if (!container) return;
    // 只在没有消息时显示空状态
    if (container.querySelector('.message')) return;
    if (container.querySelector('.empty-state')) return;

    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'empty-state';
    emptyDiv.innerHTML = `
      <div class="empty-state-icon">🛡️</div>
      <h2 class="empty-state-title">反诈卫士</h2>
      <p class="empty-state-desc">AI驱动的智能反诈对话系统</p>
      <p class="empty-state-hint">输入你遇到的情况开始咨询，或点击下方功能探索</p>
    `;
    container.appendChild(emptyDiv);
  }

  // 隐藏空状态
  hideEmptyState() {
    const el = this.elements.chatMessages?.querySelector('.empty-state');
    if (el) el.remove();
  }

  showSuggestions(suggestions) {
    const area = this.elements.suggestionArea;
    area.innerHTML = '';
    suggestions.forEach(text => {
      const chip = document.createElement('button');
      chip.className = 'suggestion-chip';
      chip.textContent = text;
      chip.addEventListener('click', () => {
        this.elements.userInput.value = text;
        this.handleSend();
      });
      area.appendChild(chip);
    });
  }

  formatMessage(text) {
    if (!text) return '';
    // 先转义HTML特殊字符，防止XSS和DOM破坏
    let safe = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    // 转换Markdown样式标记为HTML
    safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/__(.*?)__/g, '<em>$1</em>');
    // 转换换行为<br>
    safe = safe.replace(/\n/g, '<br>');
    // 识别电话号码（但避免匹配已经转义的内容）
    safe = safe.replace(/(\d{3,4}[-]\d{7,8}|\d{11})/g, '<a href="tel:$1" style="color: var(--primary); font-weight: 600;">$1</a>');
    return safe;
  }

  showTyping() {
    this.hideTyping();
    const div = document.createElement('div');
    div.className = 'typing-indicator';
    div.id = 'typing-indicator';
    for (let i = 0; i < 3; i++) {
      const span = document.createElement('span');
      div.appendChild(span);
    }
    this.elements.chatMessages.appendChild(div);
    this.scrollToBottom();
  }

  hideTyping() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
  }

  scrollToBottom() {
    if (!this.elements.chatMessages) return;
    // 使用 requestAnimationFrame 确保在渲染完成后滚动
    requestAnimationFrame(() => {
      try {
        this.elements.chatMessages.scrollTo({
          top: this.elements.chatMessages.scrollHeight,
          behavior: 'smooth'
        });
      } catch (e) {
        // fallback
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
      }
    });
  }

  showToast(message) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
  }

  // ========== 情景模拟 ==========

  async openScenarioList() {
    try {
      const res = await fetch('/api/scenario/list');
      const data = await res.json();
      this.showScenarioCards(data.scenarios);
      this.elements.scenarioModal.classList.add('active');
    } catch (e) {
      this.showToast('加载情景失败');
    }
  }

  showScenarioCards(scenarios) {
    const list = this.elements.scenarioList;
    list.innerHTML = '';
    list.style.display = 'block';
    this.elements.scenarioScene.style.display = 'none';

    scenarios.forEach(s => {
      const card = document.createElement('div');
      card.className = 'scenario-card';
      card.innerHTML = `
        <div class="sc-title">
          <span>${s.title}</span>
          <span class="sc-diff diff-${s.difficulty}">
            ${['简单', '中等', '困难'][s.difficulty - 1] || '简单'}
          </span>
        </div>
        <div class="sc-desc">${s.description}</div>
        <div class="sc-status">
          ${s.completed ? `✅ 已完成 最高分: ${s.best_score}` : '⏳ 未开始'}
        </div>
      `;
      card.addEventListener('click', () => this.startScenario(s.id));
      list.appendChild(card);
    });
  }

  async startScenario(scenarioId) {
    try {
      const res = await fetch('/api/scenario/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId, user_id: this.userId })
      });
      const data = await res.json();

      this.scenarioState = {
        id: scenarioId,
        step: data.step,
        totalSteps: data.total_steps,
        score: 0,
        scenarioTitle: data.scenario,
        fraudType: data.fraud_type,
        completionMessage: data.completion_message,
        nextStepData: null
      };

      this.renderScenarioStep(data);
    } catch (e) {
      this.showToast('开始情景失败');
    }
  }

  renderScenarioStep(data) {
    const list = this.elements.scenarioList;
    list.style.display = 'none';
    const scene = this.elements.scenarioScene;
    scene.style.display = 'block';

    scene.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 16px;">${data.scenario}</h3>
          <span style="font-size: 12px; color: var(--text-secondary);">
            步骤 ${data.step}/${data.totalSteps}
            ${data.fraud_type ? ` | 类型: ${data.fraud_type}` : ''}
          </span>
        </div>
        <div style="font-size: 14px; font-weight: 600; color: var(--primary);">
          得分: ${this.scenarioState?.score || 0}
        </div>
      </div>
      <div class="scene-npc">
        <div class="npc-label">💬 对方说:</div>
        <div class="npc-text">${data.npc_message}</div>
      </div>
      <div style="margin-top: 16px;">
        <div style="font-weight: 600; margin-bottom: 8px; font-size: 14px;">你的选择:</div>
        ${data.choices.map((c, i) => `
          <button class="choice-btn" data-index="${i}">${c.text}</button>
        `).join('')}
      </div>
      <div id="scene-feedback"></div>
      <div id="scene-next" style="display: none; margin-top: 16px;"></div>
    `;

    scene.querySelectorAll('.choice-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const index = parseInt(btn.dataset.index);
        this.handleScenarioChoice(index, scene, data);
      });
    });
  }

  async handleScenarioChoice(index, sceneContainer, currentData) {
    const choices = sceneContainer.querySelectorAll('.choice-btn');
    choices.forEach((btn, i) => {
      btn.disabled = true;
      if (i === index) {
        btn.classList.add(currentData.choices[i].is_safe ? 'selected-safe' : 'selected-unsafe');
      }
    });

    const choice = currentData.choices[index];
    this.scenarioState.score += choice.score;

    const feedback = sceneContainer.querySelector('#scene-feedback');
    feedback.innerHTML = `
      <div class="feedback-box ${choice.is_safe ? 'safe' : 'unsafe'}">
        <strong>${choice.is_safe ? '✅ ' : '❌ '}${choice.feedback}</strong>
        <br>得分: ${choice.score > 0 ? '+' : ''}${choice.score}
      </div>
    `;

    try {
      const res = await fetch('/api/scenario/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: this.scenarioState.id,
          step: this.scenarioState.step,
          choice: index,
          user_id: this.userId
        })
      });
      const data = await res.json();

      const nextDiv = sceneContainer.querySelector('#scene-next');
      nextDiv.style.display = 'block';

      if (data.has_next && data.next_step) {
        this.scenarioState.nextStepData = data.next_step;
        this.scenarioState.step = data.next_step.step;
        nextDiv.innerHTML = `<button class="btn-icon send" style="width: auto; padding: 10px 24px; border-radius: 20px; font-size: 14px;" onclick="app.continueScenario()">👉 下一步</button>`;
      } else {
        const totalScore = Math.max(0, this.scenarioState.score);
        const maxScore = 60;
        const percentage = Math.round((totalScore / maxScore) * 100);

        let grade = '❌ 需要提高';
        let gradeColor = 'var(--danger)';
        if (percentage >= 80) { grade = '🛡️ 反诈达人'; gradeColor = 'var(--success)'; }
        else if (percentage >= 60) { grade = '⚠️ 还需警惕'; gradeColor = 'var(--warning)'; }

        nextDiv.innerHTML = `
          <div style="text-align: center; padding: 20px;">
            <div style="font-size: 36px; margin-bottom: 8px;">🎉</div>
            <h3>情景模拟完成!</h3>
            <div style="font-size: 24px; font-weight: 700; color: ${gradeColor}; margin: 8px 0;">${grade}</div>
            <div style="font-size: 14px; color: var(--text-secondary); margin: 8px 0;">
              总分: ${totalScore} / ${maxScore} (${percentage}%)
            </div>
            <div style="margin-top: 8px; font-size: 13px; line-height: 1.6;">
              ${this.scenarioState.completionMessage || ''}
            </div>
            ${data.gamification ? `
              <div style="margin-top: 12px; padding: 12px; background: var(--primary-light); border-radius: 8px;">
                <strong>🎊 奖励!</strong><br>+${data.gamification.points_awarded} 积分
                ${data.gamification.badges_awarded?.length ? `<br>🏅 获得勋章: ${data.gamification.badges_awarded.map(b => b.badge.name).join(', ')}` : ''}
              </div>
            ` : ''}
            <button class="btn-icon send" style="width: auto; padding: 10px 24px; border-radius: 20px; font-size: 14px; margin-top: 16px;"
                    onclick="app.closeScenario()">✅ 完成</button>
          </div>
        `;
        this.loadUserProfile();
        this.loadDailyTasks();
      }
    } catch (e) {
      this.showToast('处理出错，请重试');
    }
  }

  continueScenario() {
    const scene = this.elements.scenarioScene;
    const nextDiv = scene.querySelector('#scene-next');
    nextDiv.style.display = 'none';
    if (this.scenarioState.nextStepData) {
      this.renderScenarioStep(this.scenarioState.nextStepData);
      this.scenarioState.nextStepData = null;
    }
  }

  closeScenario() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
    this.scenarioState = null;
    this.scenarioScore = 0;
  }

  // ========== 举报功能 ==========

  openReportModal() {
    this.elements.reportResult.innerHTML = '';
    this.elements.reportUrlInput.value = '';
    this.elements.reportDescInput.value = '';
    this.elements.reportModal.classList.add('active');
    this.loadReportHistory();
  }

  async loadReportHistory() {
    try {
      const res = await fetch(`/api/report/history?user_id=${this.userId}`);
      const data = await res.json();
      if (data.history?.length) {
        this.elements.reportHistory.innerHTML = `
          <div style="padding: 12px; background: var(--bg); border-radius: 8px; font-size: 13px;">
            <strong>📋 举报记录</strong> (共${data.stats?.total || 0}次)
            <br>可疑: ${data.stats?.suspicious || 0} | 安全: ${data.stats?.safe || 0}
            <br><span style="font-size: 12px;">最近: ${new Date(data.history[data.history.length-1]?.timestamp * 1000).toLocaleString()}</span>
          </div>
        `;
      }
    } catch (e) { /* ignore */ }
  }

  async handleReport() {
    const url = this.elements.reportUrlInput.value.trim();
    const desc = this.elements.reportDescInput.value.trim();
    if (!url) {
      this.showToast('请输入要举报的链接');
      return;
    }

    this.elements.reportBtn.disabled = true;
    this.elements.reportBtn.textContent = '分析中...';

    try {
      const res = await fetch('/api/report/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, description: desc, user_id: this.userId })
      });
      const data = await res.json();
      const analysis = data.url_analysis;

      this.elements.reportResult.innerHTML = `
        <div class="report-result ${analysis.is_suspicious ? 'suspicious' : 'safe'}">
          <strong>${analysis.is_suspicious ? '🚨 可疑链接!' : '✅ 链接分析完成'}</strong><br>
          <strong>风险等级:</strong> ${analysis.risk_level === 'critical' ? '⚠️ 高危' :
            analysis.risk_level === 'high' ? '🔴 高风险' :
            analysis.risk_level === 'medium' ? '🟡 中风险' : '🟢 低风险'}<br>
          <strong>域名:</strong> ${analysis.domain || '未知'}<br>
          ${analysis.details?.length ? `<strong>风险详情:</strong><br>${analysis.details.map(d => '• ' + d).join('<br>')}<br>` : ''}
          <strong>建议:</strong> ${data.advice || '保持警惕'}
        </div>
      `;

      this.loadUserProfile();
      this.loadDailyTasks();
    } catch (e) {
      this.showToast('分析失败，请重试');
    }

    this.elements.reportBtn.disabled = false;
    this.elements.reportBtn.textContent = '🔍 分析链接';
  }

  // ========== 知识库 ==========

  openKnowledgeBase() {
    this.elements.knowledgeContent.innerHTML = `
      <div style="margin-bottom: 16px;">
        <h4>📚 常见骗局类型</h4>
        <p style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">点击了解详情，或直接在对话框中问我</p>
      </div>
      <div id="kb-list">
        <button class="choice-btn" onclick="app.queryKnowledge('刷单返利')">💰 刷单返利诈骗</button>
        <button class="choice-btn" onclick="app.queryKnowledge('游戏交易')">🎮 游戏交易诈骗</button>
        <button class="choice-btn" onclick="app.queryKnowledge('冒充公检法')">👮 冒充公检法诈骗</button>
        <button class="choice-btn" onclick="app.queryKnowledge('虚假投资')">📈 虚假投资诈骗</button>
        <button class="choice-btn" onclick="app.queryKnowledge('校园贷')">🏫 校园贷诈骗</button>
      </div>
      <div id="kb-result" style="margin-top: 16px;"></div>
    `;
    this.elements.knowledgeModal.classList.add('active');
  }

  async queryKnowledge(type) {
    this.showToast(`正在查询: ${type}`);
    this.sendMessage({ message: `告诉我${type}诈骗的详解` });
    setTimeout(() => {
      document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
    }, 500);
  }

  // ========== 排行榜 ==========

  async openLeaderboard() {
    this.elements.leaderboardModal.classList.add('active');
    this.elements.leaderboardContent.innerHTML = '<p style="color: var(--text-secondary);">加载中...</p>';

    try {
      const res = await fetch(`/api/user/leaderboard?user_id=${this.userId}`);
      const data = await res.json();

      let html = '';
      if (data.user_rank) {
        html += `<div style="background: var(--primary-light); padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 14px;">
          <strong>你的排名:</strong> 第 ${data.user_rank.rank} 名
          | ⭐ ${data.user_rank.points} 积分 | Lv.${data.user_rank.level_num} ${data.user_rank.level}
        </div>`;
      }

      if (data.leaderboard?.length) {
        html += `<div style="font-size: 13px;">`;
        data.leaderboard.forEach((u, i) => {
          const medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${u.rank}`;
          const isMe = u.user_id === this.userId.slice(0, 8);
          html += `<div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); ${isMe ? 'background: var(--primary-light); margin: 0 -12px; padding: 10px 12px; border-radius: 8px;' : ''}">
            <span>${medal} <strong>${u.user_id}</strong> ${isMe ? '(你)' : ''}</span>
            <span>⭐ ${u.points} | Lv.${u.level_num} | 🏅 ${u.badges}枚</span>
          </div>`;
        });
        html += `</div>`;
      } else {
        html += '<p style="color: var(--text-secondary);">暂无排行榜数据</p>';
      }

      this.elements.leaderboardContent.innerHTML = html;
    } catch (e) {
      this.elements.leaderboardContent.innerHTML = '<p style="color: var(--danger);">加载失败</p>';
    }
  }

  // ========== 用户资料 ==========

  async loadUserProfile() {
    try {
      const res = await fetch(`/api/user/profile?user_id=${this.userId}`);
      const data = await res.json();

      this.userPoints = data.points;
      this.userLevel = data.level;

      // 更新侧边栏
      document.querySelector('.level-badge').textContent = `Lv.${data.level.level} ${data.level.name}`;
      document.querySelector('.username').textContent = `用户 ${this.userId}`;

      // 连续签到
      if (data.login_streak > 0) {
        this.elements.streakDisplay.style.display = 'block';
        this.elements.streakCount.textContent = data.login_streak;
      }

      // 积分卡片
      const gArea = this.elements.profileArea;
      if (gArea) {
        const nextLevel = data.next_level;
        gArea.innerHTML = `
          <div class="gamification-card">
            <div class="level-info">
              <span class="level-name">${data.level.name}</span>
              <span class="level-num">Lv.${data.level.level}</span>
            </div>
            <div class="progress-bar">
              <div class="fill" style="width: ${data.progress.current_level_progress}%"></div>
            </div>
            <div class="points-display">
              <span class="stat">⭐ ${data.points} 积分</span>
              <span class="stat">🏅 ${data.progress.total_badges}/${data.progress.available_badges} 勋章</span>
              <span class="stat">🎮 ${data.scenario_count || 0} 通关</span>
            </div>
            ${nextLevel ? `<div style="font-size: 11px; margin-top: 4px; opacity: 0.7;">距 ${nextLevel.name} 还需 ${data.progress.points_to_next} 积分</div>` : ''}
          </div>
        `;
      }

      // 勋章
      const badgesContainer = this.elements.badgesContainer;
      if (badgesContainer) {
        if (data.badges?.length) {
          badgesContainer.innerHTML = data.badges.map(b =>
            `<div class="badge-item" title="${b.description}"><span class="badge-icon">${b.icon}</span>${b.name}</div>`
          ).join('');
        } else {
          badgesContainer.innerHTML = '<span style="font-size: 13px; color: var(--text-secondary);">完成对话或闯关获取勋章</span>';
        }
      }

    } catch (e) { /* ignore */ }
  }

  // ========== 每日任务 ==========

  async loadDailyTasks() {
    try {
      const res = await fetch(`/api/user/daily-tasks?user_id=${this.userId}`);
      const data = await res.json();

      const area = this.elements.dailyTasksArea;
      if (!data.tasks?.length) {
        area.innerHTML = '';
        return;
      }

      const allDone = data.tasks.every(t => t.completed);
      area.innerHTML = `
        <div class="daily-tasks-toggle" onclick="app.toggleDailyTasks(this)">
          📋 每日任务 ${allDone ? '✅' : `(${data.tasks.filter(t => t.completed).length}/${data.tasks.length})`}
        </div>
        <div class="daily-tasks-list" style="display: none;">
          ${data.tasks.map(t => `
            <div class="daily-task-item ${t.completed ? 'completed' : ''}">
              <span>${t.icon}</span>
              <span style="flex:1; font-size: 12px;">${t.name}</span>
              <span style="font-size: 11px;">${t.progress}/${t.target}</span>
              <span style="font-size: 11px;">+${t.points}⭐</span>
              ${t.completed ? '<span style="font-size: 11px;">✅</span>' : ''}
            </div>
          `).join('')}
        </div>
      `;
    } catch (e) { /* ignore */ }
  }

  toggleDailyTasks(el) {
    const list = el.nextElementSibling;
    list.style.display = list.style.display === 'none' ? 'block' : 'none';
  }

  // ========== 历史对话 ==========

  async openHistory() {
    this.elements.historyModal.classList.add('active');
    this.loadHistoryList();
  }

  async loadHistoryList() {
    const list = this.elements.historyList;
    if (!list) return;
    list.innerHTML = '<p style="color: var(--text-secondary); font-size: 14px; padding: 20px 0; text-align: center;">⏳ 加载中...</p>';

    try {
      const res = await fetch(`/api/history?user_id=${this.userId}&include_alerts=true`);
      const data = await res.json();
      const history = data.history || [];

      if (!history.length) {
        list.innerHTML = '<div style="text-align:center; padding:40px 20px;"><div style="font-size:48px; margin-bottom:12px;">📭</div><p style="color:var(--text-secondary);">暂无对话记录</p><p style="font-size:12px; color:var(--text-secondary); margin-top:4px;">开始对话后，历史记录将在这里展示</p></div>';
        return;
      }

      // 按日期分组
      const groups = {};
      for (const msg of history) {
        const date = msg.created_at ? msg.created_at.substring(0, 10) : '未知日期';
        if (!groups[date]) groups[date] = [];
        groups[date].push(msg);
      }

      let html = '';
      const dateKeys = Object.keys(groups).sort().reverse();
      for (const date of dateKeys) {
        const msgs = groups[date];
        const today = new Date().toISOString().substring(0, 10);
        const yesterday = new Date(Date.now() - 86400000).toISOString().substring(0, 10);
        let dateLabel = date;
        if (date === today) dateLabel = '📅 今天';
        else if (date === yesterday) dateLabel = '📅 昨天';
        else dateLabel = '📅 ' + date;

        html += `<div style="margin-bottom:12px;">
          <div style="font-size:12px; font-weight:600; color:var(--text-secondary); padding:4px 0; border-bottom:1px solid var(--border); margin-bottom:6px;">${dateLabel} <span style="font-weight:400; font-size:11px;">(${msgs.length} 条消息)</span></div>`;

        // 显示每组中的消息摘要（最多6条）
        const displayMsgs = msgs.slice(-6);
        for (const msg of displayMsgs) {
          const roleLabel = msg.role === 'user' ? '你' : '🤖 反诈助手';
          const roleColor = msg.role === 'user' ? 'var(--primary)' : 'var(--success)';
          const prefix = msg.role === 'user' ? '💬' : '💡';
          const content = (msg.content || '').substring(0, 60) + ((msg.content || '').length > 60 ? '...' : '');
          const privacyTag = msg.has_privacy_alert ? '<span style="font-size:10px; color:var(--primary); margin-left:4px;">🔒</span>' : '';

          html += `<div class="history-item" data-msg-id="${msg.id || ''}" style="padding:6px 10px; cursor:pointer; border-radius:6px; margin:2px 0; display:flex; align-items:flex-start; gap:6px; transition:background 0.15s;" onmouseover="this.style.background='var(--primary-light)'" onmouseout="this.style.background='transparent'">
            <span style="font-size:12px; margin-top:2px; color:${roleColor};">${prefix}</span>
            <div style="flex:1; min-width:0;">
              <div style="font-size:11px; font-weight:600; color:${roleColor};">${roleLabel}${privacyTag}</div>
              <div style="font-size:12px; color:var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${this.escapeHtml(content)}</div>
            </div>
            <span style="font-size:10px; color:var(--text-secondary); white-space:nowrap; margin-top:4px;">${msg.created_at ? msg.created_at.substring(11, 16) : ''}</span>
          </div>`;
        }
        if (msgs.length > 6) {
          html += `<div style="font-size:11px; color:var(--text-secondary); text-align:center; padding:2px 0;">… 还有 ${msgs.length - 6} 条消息</div>`;
        }
        html += '</div>';
      }

      list.innerHTML = html;

      // 点击历史消息可重新发送/查看
      list.querySelectorAll('.history-item').forEach(el => {
        el.addEventListener('click', () => {
          const msgDivs = el.parentElement?.querySelectorAll('.history-item');
          if (msgDivs) msgDivs.forEach(d => d.style.background = 'transparent');
          el.style.background = 'var(--primary-light)';
        });
        // 双击将消息填入输入框
        el.addEventListener('dblclick', () => {
          const textEl = el.querySelector('div:last-child div:last-child');
          if (textEl) {
            this.elements.userInput.value = textEl.textContent || '';
            this.elements.historyModal.classList.remove('active');
            this.elements.userInput.focus();
          }
        });
      });

    } catch (e) {
      list.innerHTML = `<p style="color: var(--danger); padding:20px; text-align:center;">😓 加载失败: ${e.message}</p>`;
    }
  }

  async loadHistoryToChat() {
    this.elements.historyModal.classList.remove('active');
    try {
      const res = await fetch(`/api/history/memory?user_id=${this.userId}`);
      const data = await res.json();
      if (data.has_history && data.history.length > 0) {
        // 清空当前对话
        this.elements.chatMessages.innerHTML = '';
        this.elements.suggestionArea.innerHTML = '';
        this._isSending = false;

        const memoryDiv = document.createElement('div');
        memoryDiv.className = 'memory-divider';
        memoryDiv.innerHTML = '<span>📜 加载历史对话</span>';
        this.elements.chatMessages.appendChild(memoryDiv);

        for (const msg of data.history) {
          if (msg.role === 'user') {
            this.addMessage(msg.content, 'user');
          } else if (msg.role === 'assistant') {
            this.addMessage(msg.content, 'bot', { type: msg.msg_type, riskLevel: msg.risk_level });
          }
        }

        const continueDiv = document.createElement('div');
        continueDiv.className = 'memory-divider';
        continueDiv.innerHTML = '<span>💬 继续对话</span>';
        this.elements.chatMessages.appendChild(continueDiv);
        this.showToast('✅ 已加载历史对话');
      } else {
        this.showToast('📭 没有历史对话');
      }
    } catch (e) {
      this.showToast('😓 加载失败');
    }
  }

  escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ========== 清空对话 ==========

  async clearChat() {
    this.elements.chatMessages.innerHTML = '';
    this.elements.suggestionArea.innerHTML = '';
    this._isSending = false;
    try {
      const res = await fetch('/api/clear', { method: 'POST' });
      const data = await res.json();
      if (data.privacy_cleared) {
        this.showToast('🔒 对话和隐私数据已安全清除');
        this.updatePrivacyStatus(0);
      } else {
        this.showToast('对话已清空');
      }
    } catch (e) { /* ignore */ }
    this.showEmptyState();
    this.sendMessage({ message: '', isAuto: true });
  }

  // ========== v3.0 暗色模式 ==========

  initTheme() {
    const toggle = document.getElementById('theme-toggle');
    const saved = localStorage.getItem('antifraud-theme');
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.setAttribute('data-theme', 'dark');
      toggle.textContent = '☀️';
    }
    toggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      toggle.textContent = next === 'dark' ? '☀️' : '🌙';
      localStorage.setItem('antifraud-theme', next);
    });
  }

  // ========== v3.0 智能分析面板 ==========

  showFeaturePanel(icon, title, bodyHTML) {
    const panel = document.getElementById('feature-panel');
    document.getElementById('feature-panel-icon').textContent = icon;
    document.getElementById('feature-panel-title').textContent = title;
    document.getElementById('feature-panel-body').innerHTML = bodyHTML;
    document.getElementById('feature-result').classList.remove('show');
    panel.style.display = 'block';
    // 滚动面板到可见区域
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  showFeatureResult(html, isDanger = false) {
    const result = document.getElementById('feature-result');
    result.innerHTML = html;
    result.classList.add('show');
    if (isDanger) result.classList.add('danger');
    else result.classList.remove('danger');
  }

  // ========== v3.0 语义深度分析 ==========

  showSmartAnalyze() {
    this.showFeaturePanel('🧠', '语义深度分析', `
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">
        输入任意文本，AI将用语义理解引擎深度分析诈骗风险
      </p>
      <div class="input-wrapper" style="margin-bottom:8px;">
        <textarea id="smart-text" placeholder="描述你遇到的情况，或粘贴可疑的对话内容..."
          rows="3" style="width:100%;border:1px solid var(--border);border-radius:8px;padding:10px;font-family:inherit;font-size:13px;resize:vertical;background:var(--bg);color:var(--text);"></textarea>
      </div>
      <button id="smart-analyze-btn" style="padding:8px 20px;background:linear-gradient(135deg,#8b5cf6,#6366f1);color:#fff;border:none;border-radius:16px;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;">
        🧠 开始分析
      </button>
      <span id="smart-loading" style="display:none;margin-left:8px;font-size:12px;color:var(--text-secondary);">分析中...</span>
    `);

    document.getElementById('smart-analyze-btn').addEventListener('click', async () => {
      const text = document.getElementById('smart-text').value.trim();
      if (!text) { this.showToast('请输入要分析的文本'); return; }
      const btn = document.getElementById('smart-analyze-btn');
      const loading = document.getElementById('smart-loading');
      btn.disabled = true;
      loading.style.display = 'inline';
      try {
        const res = await fetch('/api/analyze/text', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, user_id: this.userId }),
        });
        const data = await res.json();
        const hasRisk = data.audio_style_analysis?.has_fraud_indicators;
        const detections = data.audio_style_analysis?.detections || [];
        const intent = data.semantic_analysis?.intent || 'unknown';
        const confidence = data.semantic_analysis?.confidence || 0;
        const frauds = data.semantic_analysis?.fraud_matches || [];
        let html = `<div style="font-size:13px;">`;
        html += `<p><strong>识别意图:</strong> ${intent} (置信度: ${(confidence*100).toFixed(0)}%)</p>`;
        if (frauds.length > 0) {
          html += `<p><strong>匹配诈骗类型:</strong> ${frauds.map(f => `${f.type}(${(f.confidence*100).toFixed(0)}%)`).join(', ')}</p>`;
        }
        if (detections.length > 0) {
          html += `<p style="color:var(--danger);"><strong>⚠️ 检测到 ${detections.length} 个风险特征:</strong></p><ul>`;
          detections.forEach(d => { html += `<li>${d.type}: ${d.detail} [${d.risk}]</li>`; });
          html += `</ul>`;
        }
        if (!hasRisk && frauds.length === 0) {
          html += `<p style="color:var(--success);">✅ 未检测到明显诈骗特征</p>`;
        }
        html += `</div>`;
        this.showFeatureResult(html, hasRisk);
      } catch (e) {
        this.showFeatureResult(`<p style="color:var(--danger);">分析失败: ${e.message}</p>`, true);
      }
      btn.disabled = false;
      loading.style.display = 'none';
    });
  }

  // ========== v3.0 截图诈骗识别 ==========

  showImageDetect() {
    this.showFeaturePanel('🔍', '截图诈骗识别', `
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">
        上传可疑的聊天截图、APP界面、短信截图，AI自动识别诈骗特征
      </p>
      <label class="upload-zone" id="image-upload-zone">
        <input type="file" id="image-file-input" accept="image/*">
        <div class="upload-icon">📸</div>
        <div class="upload-text">点击上传图片 或 拖拽到此处</div>
      </label>
      <div id="image-preview" style="display:none;margin:8px 0;text-align:center;"></div>
      <button id="image-analyze-btn" style="padding:8px 20px;background:linear-gradient(135deg,#8b5cf6,#6366f1);color:#fff;border:none;border-radius:16px;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;display:none;">
        🔍 分析截图
      </button>
      <span id="image-loading" style="display:none;margin-left:8px;font-size:12px;color:var(--text-secondary);">识别中...</span>
    `);

    const fileInput = document.getElementById('image-file-input');
    const preview = document.getElementById('image-preview');
    const analyzeBtn = document.getElementById('image-analyze-btn');
    let selectedFile = null;

    fileInput.addEventListener('change', (e) => {
      selectedFile = e.target.files[0];
      if (selectedFile) {
        preview.style.display = 'block';
        preview.innerHTML = `<img src="${URL.createObjectURL(selectedFile)}" style="max-width:200px;max-height:200px;border-radius:8px;"><br><span style="font-size:12px;color:var(--text-secondary);">${selectedFile.name}</span>`;
        analyzeBtn.style.display = 'inline-block';
      }
    });

    analyzeBtn.addEventListener('click', async () => {
      if (!selectedFile) return;
      const loading = document.getElementById('image-loading');
      analyzeBtn.disabled = true;
      loading.style.display = 'inline';
      const formData = new FormData();
      formData.append('file', selectedFile);
      try {
        const res = await fetch('/api/analyze/image', { method: 'POST', body: formData });
        const data = await res.json();
        const hasRisk = data.has_fraud_indicators;
        let html = `<div style="font-size:13px;">`;
        html += `<p><strong>风险等级:</strong> ${data.risk_level || 'none'}</p>`;
        html += `<p>${data.summary || ''}</p>`;
        if (data.detections && data.detections.length > 0) {
          html += `<p style="color:var(--danger);"><strong>检测到:</strong></p><ul>`;
          data.detections.forEach(d => { html += `<li>${d.type}: "${d.matched_text}"</li>`; });
          html += `</ul>`;
        }
        if (data.extracted_text) {
          html += `<details style="margin-top:8px;"><summary style="cursor:pointer;font-size:12px;color:var(--text-secondary);">查看识别文字</summary><p style="font-size:11px;color:var(--text-secondary);white-space:pre-wrap;margin-top:4px;">${this.escapeHtml(data.extracted_text)}</p></details>`;
        }
        html += `</div>`;
        this.showFeatureResult(html, hasRisk);
      } catch (e) {
        this.showFeatureResult(`<p style="color:var(--danger);">OCR引擎未安装，请安装: pip install easyocr</p><p style="font-size:12px;color:var(--text-secondary);">当前环境仅支持规则引擎离线模式</p>`, false);
      }
      analyzeBtn.disabled = false;
      loading.style.display = 'none';
    });
  }

  // ========== v3.0 语音诈骗检测 ==========

  showAudioDetect() {
    this.showFeaturePanel('🎤', '语音诈骗检测', `
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">
        粘贴可疑通话的文字记录，或输入可疑话术，AI分析是否包含诈骗特征
      </p>
      <div class="input-wrapper" style="margin-bottom:8px;">
        <textarea id="audio-text" placeholder="粘贴通话内容或输入可疑话术..."
          rows="4" style="width:100%;border:1px solid var(--border);border-radius:8px;padding:10px;font-family:inherit;font-size:13px;resize:vertical;background:var(--bg);color:var(--text);"></textarea>
      </div>
      <button id="audio-analyze-btn" style="padding:8px 20px;background:linear-gradient(135deg,#8b5cf6,#6366f1);color:#fff;border:none;border-radius:16px;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;">
        🎤 检测诈骗话术
      </button>
      <span id="audio-loading" style="display:none;margin-left:8px;font-size:12px;color:var(--text-secondary);">分析中...</span>
    `);

    document.getElementById('audio-analyze-btn').addEventListener('click', async () => {
      const text = document.getElementById('audio-text').value.trim();
      if (!text) { this.showToast('请输入通话内容'); return; }
      const btn = document.getElementById('audio-analyze-btn');
      const loading = document.getElementById('audio-loading');
      btn.disabled = true;
      loading.style.display = 'inline';
      try {
        const res = await fetch('/api/analyze/audio', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, user_id: this.userId }),
        });
        const data = await res.json();
        const hasRisk = data.has_fraud_indicators;
        let html = `<div style="font-size:13px;">`;
        html += `<p><strong>风险等级:</strong> <span style="color:${hasRisk ? 'var(--danger)' : 'var(--success)'};">${data.risk_level || 'none'}</span></p>`;
        if (data.detections && data.detections.length > 0) {
          html += `<p style="color:var(--danger);"><strong>检测到 ${data.detections.length} 个诈骗特征:</strong></p><ul>`;
          data.detections.forEach(d => { html += `<li>[${d.risk}] ${d.type}: ${d.detail}</li>`; });
          html += `</ul>`;
        } else {
          html += `<p style="color:var(--success);">✅ 未检测到明显诈骗话术</p>`;
        }
        html += `</div>`;
        this.showFeatureResult(html, hasRisk);
      } catch (e) {
        this.showFeatureResult(`<p style="color:var(--danger);">分析失败: ${e.message}</p>`, true);
      }
      btn.disabled = false;
      loading.style.display = 'none';
    });
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// ========== 启动应用 ==========
const app = new AntiFraudApp();
