import { expect, test } from '@playwright/test'

test.describe('遗址公园研究门户', () => {
  test('首页使用顶部导航且没有全局侧栏', async ({ page, isMobile }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /探索遗址公园/ })).toBeVisible()
    await expect(page.locator('.portal-header')).toBeVisible()
    await expect(page.locator('.aside')).toHaveCount(0)
    if (isMobile) {
      await page.getByRole('button', { name: '打开移动导航' }).click()
      await expect(page.locator('.mobile-nav')).toBeVisible()
      await page.locator('.mobile-nav').getByText('遗址公园', { exact: true }).click()
    } else {
      await page.locator('.portal-nav').getByText('遗址公园', { exact: true }).click()
    }
    await expect(page).toHaveURL(/\/parks/)
    await expect(page.locator('.portal-nav__item.active')).toHaveText('遗址公园')
    await expect(page.locator('.page-hero')).toHaveCount(0)
  })

  test('遗址筛选和详情使用真实接口', async ({ page }) => {
    await page.goto('/parks')
    await expect(page.locator('.park-card').first()).toBeVisible()
    const count = await page.locator('.park-card').count()
    expect(count).toBeGreaterThan(0)
    const keyword = page.getByPlaceholder('搜索公园名称、地点')
    await keyword.fill('圆明园')
    await page.getByRole('button', { name: '查询公园' }).click()
    await expect(page.getByRole('heading', { name: '共 1 个遗址公园' })).toBeVisible()
    await page.locator('.park-card').first().getByRole('button', { name: /查看详情/ }).click()
    await expect(page).toHaveURL(/\/parks\/\d+/)
    await expect(page.locator('.detail-hero h1')).toBeVisible()
    await expect(page.getByText('评价指标明细')).toBeVisible()
  })

  test('研究工具和管理页均无全局侧栏', async ({ page }) => {
    for (const route of ['/research-data', '/parks', '/map', '/compare', '/knowledge-graph', '/assistant', '/library', '/bibliometrics', '/about', '/data-management']) {
      await page.goto(route)
      await expect(page.locator('.portal-header')).toBeVisible()
      await expect(page.locator('.aside')).toHaveCount(0)
    }
    await expect(page.getByText('遗址公园', { exact: true }).last()).toBeVisible()
  })

  test('地图明确展示真实服务或配置错误状态', async ({ page, isMobile }) => {
    await page.goto('/map')
    await expect(page.locator('.portal-nav__item.active')).toHaveText('地图浏览')
    await expect(page.locator('.map-canvas')).toBeVisible()
    const ready = await page.locator('.amap-container').count()
    if (!ready) await expect(page.getByText('地图服务暂不可用')).toBeVisible()
    if (isMobile) {
      await page.getByRole('button', { name: /筛选/ }).click()
      await expect(page.getByRole('heading', { name: '筛选遗址公园' })).toBeVisible()
    } else {
      await page.locator('.map-filter-panel').getByRole('button', { name: '城市型', exact: true }).click()
      await page.getByRole('button', { name: '筛选公园', exact: true }).click()
      await expect(page.locator('.map-result-hint').getByText(/3/).first()).toBeVisible()
    }
  })

  test('对比分析使用真实公园评分', async ({ page }) => {
    await page.goto('/compare?park_ids=1,2,3')
    await expect(page.locator('.selected-parks article')).toHaveCount(3)
    await expect(page.locator('.compare-main-grid canvas')).toHaveCount(2)
    await page.getByText('数据表格', { exact: true }).click()
    await expect(page.locator('.compare-table tbody tr')).toHaveCount(3)
  })

  test('知识库搜索和 AI 输入框可用', async ({ page }) => {
    await page.goto('/library')
    const search = page.getByPlaceholder(/搜索文献标题/)
    await expect(search).toBeVisible()
    await search.fill('遗址保护')
    await search.press('Enter')
    await page.goto('/assistant')
    await expect(page.getByPlaceholder(/输入您的问题/)).toBeVisible()
  })
})
