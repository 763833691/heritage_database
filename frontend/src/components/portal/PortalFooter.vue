<template>
  <footer class="portal-footer">
    <div class="portal-footer__inner">
      <div class="portal-footer__brand">
        <div class="portal-footer__title">
          <span class="portal-footer__mark"><el-icon><OfficeBuilding /></el-icon></span>
          <strong>遗址公园研究平台</strong>
        </div>
        <p>汇聚遗址公园数据、知识与研究工具，为文化遗产保护和科学决策提供可信支持。</p>
      </div>
      <div class="portal-footer__links">
        <router-link to="/about">关于我们</router-link>
        <a href="mailto:heritage@example.com">联系我们</a>
        <button type="button">用户协议</button>
        <button type="button">隐私政策</button>
        <button type="button">数据来源说明</button>
      </div>
      <div class="portal-footer__meta">
        <span>© 2026 遗址公园研究平台</span>
        <span>地图服务版权及审图信息以地图页面展示为准</span>
      </div>
    </div>
  </footer>
</template>

<style scoped lang="scss">
.portal-footer { margin-top: 72px; border-top: 1px solid var(--border); background: #fff; }
.portal-footer__inner { width: min(100% - 40px, 1440px); margin: 0 auto; padding: 42px 0 28px; display: grid; grid-template-columns: minmax(260px, 1.3fr) 1fr; gap: 28px 64px; }
.portal-footer__brand p { max-width: 560px; margin: 12px 0 0; color: var(--text-secondary); line-height: 1.8; font-size: 13px; }
.portal-footer__title { display: flex; align-items: center; gap: 10px; color: var(--text-primary); }
.portal-footer__mark { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; color: #fff; background: var(--brand-600); }
.portal-footer__links { display: flex; flex-wrap: wrap; justify-content: flex-end; align-content: start; gap: 12px 24px; }
.portal-footer__links a, .portal-footer__links button { color: var(--text-secondary); font: inherit; font-size: 13px; text-decoration: none; border: 0; background: none; padding: 0; cursor: pointer; }
.portal-footer__links a:hover, .portal-footer__links button:hover { color: var(--brand-600); }
.portal-footer__meta { grid-column: 1 / -1; display: flex; justify-content: space-between; padding-top: 22px; border-top: 1px solid var(--border); color: var(--text-tertiary); font-size: 12px; }
@media (max-width: 760px) {
  .portal-footer { margin-top: 48px; }
  .portal-footer__inner { width: calc(100% - 32px); grid-template-columns: 1fr; }
  .portal-footer__links { justify-content: flex-start; }
  .portal-footer__meta { display: grid; gap: 8px; }
}
</style>
