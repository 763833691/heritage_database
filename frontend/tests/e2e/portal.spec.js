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
    for (const route of ['/research-data', '/field-gallery', '/parks', '/map', '/compare', '/knowledge-graph', '/assistant', '/library', '/bibliometrics', '/about', '/data-management']) {
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
    await expect.poll(async () => {
      if (await page.locator('.amap-container').count()) return 'ready'
      if (await page.getByText(/地图服务(暂不可用|加载失败)/).count()) return 'error'
      return 'loading'
    }, { timeout: 20000 }).not.toBe('loading')
    if (isMobile) {
      await page.getByRole('button', { name: '筛选', exact: true }).click()
      await expect(page.getByRole('heading', { name: '筛选遗址公园' })).toBeVisible()
    } else {
      await page.locator('.map-side-panel').getByRole('button', { name: '城市型', exact: true }).click()
      await page.getByRole('button', { name: '筛选公园', exact: true }).click()
      await expect(page.locator('.map-side-panel').getByText(/公园列表/)).toBeVisible()
      await expect(page.locator('.map-side-panel .map-park-card').first()).toBeVisible()
    }
  })

  test('对比分析使用真实公园评分', async ({ page }) => {
    await page.goto('/compare?park_ids=1,2,3')
    await expect(page.locator('.selected-parks article')).toHaveCount(3)
    await expect(page.locator('.compare-main-grid canvas')).toHaveCount(2)
    await page.getByText('数据表格', { exact: true }).click()
    await expect(page.locator('.compare-table tbody tr')).toHaveCount(3)
  })

  test('田野影像总览展示全部真实照片', async ({ page }) => {
    await page.goto('/field-gallery')
    await expect(page.locator('.portal-nav__item.active')).toHaveText('田野影像')
    await expect(page.getByText('1,028').first()).toBeVisible()
    await expect(page.locator('.fg-wall-item').first()).toBeVisible()
    await expect(page.locator('.fg-wall-item')).toHaveCount(24)
    await expect(page.getByText('9').first()).toBeVisible()
  })

  test('研究数据热力图与公园调研记录真实可用', async ({ page }) => {
    await page.goto('/research-data')
    await expect(page.getByText('田野调研覆盖')).toBeVisible()
    await expect(page.getByRole('heading', { name: '公园 × 指标评分热力图' })).toBeVisible()
    await expect(page.locator('.coverage-grid .portal-stat-card')).toHaveCount(5)
    await page.goto('/parks/7')
    await expect(page.getByRole('heading', { name: '调研记录' })).toBeVisible()
    await expect(page.locator('.survey-task-list article').first()).toBeVisible()
    await expect(page.getByRole('button', { name: /导出 Excel/ }).first()).toBeVisible()
  })

  test('全站搜索分组展示公园与文献', async ({ page, isMobile }) => {
    test.skip(isMobile, '移动端头部隐藏搜索入口，仅验证桌面端')
    await page.goto('/')
    await page.getByRole('button', { name: '打开全站搜索' }).click()
    await page.getByPlaceholder('搜索遗址公园、文献或指标').fill('圆明园')
    await page.getByRole('button', { name: '搜索', exact: true }).click()
    await expect(page.locator('.global-search-results h4').first()).toBeVisible()
    await page.locator('.global-search-results section').first().locator('button').first().click()
    await expect(page).toHaveURL(/\/parks\/\d+/)
  })

  test('知识库排序按钮可切换', async ({ page }) => {
    await page.goto('/library')
    await expect(page.locator('.kb-results-bar button.active')).toHaveText('相关性')
    await page.getByRole('button', { name: '被引量' }).click()
    await expect(page.locator('.kb-results-bar button.active')).toHaveText('被引量')
  })

  test('数据管理提供公园封面上传入口', async ({ page }) => {
    await page.goto('/data-management')
    await expect(page.getByRole('columnheader', { name: '封面' })).toBeVisible()
    await expect(page.getByText('未上传').first()).toBeVisible()
    await page.getByRole('button', { name: '编辑' }).first().click()
    await expect(page.getByText('封面图片')).toBeVisible()
    await expect(page.getByRole('button', { name: '上传封面' }).first()).toBeVisible()
  })

  test('知识库可查看结构化综述数据', async ({ page }) => {
    await page.goto('/library')
    await page.getByRole('button', { name: /查看综述数据/ }).click()
    await expect(page.getByText('文献综述结构化数据')).toBeVisible()
    await expect(page.getByText('高频关键词')).toBeVisible()
  })

  test('处理流程不再展示编造的统计', async ({ page }) => {
    await page.goto('/kg/processing')
    await expect(page.getByText('文本覆盖率')).toHaveCount(0)
    await expect(page.getByText('较上次')).toHaveCount(0)
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
