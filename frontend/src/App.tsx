import { DeleteOutlined, LineChartOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Col, Divider, Form, Input, InputNumber, Layout, Modal, Popconfirm, Radio, Row, Space, Spin, Statistic, Table, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import {
  createPosition,
  deletePosition,
  fetchFundHistory,
  fetchPortfolioValuation,
  fetchPositions,
  updatePosition,
} from "./api/funds";
import { FundTrendChart } from "./components/FundTrendChart";
import { PortfolioChart } from "./components/PortfolioChart";
import type { FundHistory, PortfolioValuation, Position } from "./types";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

type PositionFormValues = {
  fund_code: string;
  position_date: string;
  trade_type: "buy" | "sell";
  amount: number;
};

function formatLocalDate(value: Date): string {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getDefaultTradeDate(): string {
  const now = new Date();
  const day = now.getDay();
  if (day === 6) {
    now.setDate(now.getDate() - 1);
  } else if (day === 0) {
    now.setDate(now.getDate() - 2);
  }
  return formatLocalDate(now);
}

function formatCurrency(value?: number | null): string {
  if (value === null || value === undefined) {
    return "--";
  }
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined) {
    return "--";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatChangeRatePercent(value?: number | null): string {
  if (value === null || value === undefined) {
    return "--";
  }
  return `${value.toFixed(2)}%`;
}

function formatPrice(value?: number | null): string {
  if (value === null || value === undefined) {
    return "--";
  }
  return `${value.toFixed(4)}`;
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "--";
  }
  return value;
}

export default function App() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioValuation | null>(null);
  const [history, setHistory] = useState<FundHistory | null>(null);
  const [selectedFundCode, setSelectedFundCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [editing, setEditing] = useState<Position | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<string | null>(null);
  const [trendModalOpen, setTrendModalOpen] = useState(false);
  const [form] = Form.useForm<PositionFormValues>();
  const selectedTradeType = Form.useWatch("trade_type", form) ?? "buy";
  const defaultPositionDate = getDefaultTradeDate();
  const todayDate = formatLocalDate(new Date());

  const loadPositions = async () => {
    const positionData = await fetchPositions();
    setPositions(positionData);
  };

  const loadPortfolio = async (refresh = false) => {
    const portfolioData = await fetchPortfolioValuation(refresh);
    setPortfolio(portfolioData);
    setLastRefreshAt(new Date().toLocaleString("zh-CN"));
  };

  const loadAll = async (refresh = false) => {
    try {
      refresh ? setRefreshing(true) : setLoading(true);
      const [positionResult, portfolioResult] = await Promise.allSettled([
        fetchPositions(),
        fetchPortfolioValuation(refresh),
      ]);
      if (positionResult.status === "fulfilled") {
        setPositions(positionResult.value);
      } else {
        message.error(positionResult.reason instanceof Error ? positionResult.reason.message : "加载持仓失败");
      }
      if (portfolioResult.status === "fulfilled") {
        setPortfolio(portfolioResult.value);
        setLastRefreshAt(new Date().toLocaleString("zh-CN"));
        try {
          const refreshedPositions = await fetchPositions();
          setPositions(refreshedPositions);
        } catch {
          // Ignore: portfolio has loaded; stale position list will be refreshed on next successful load.
        }
      } else {
        message.error(portfolioResult.reason instanceof Error ? portfolioResult.reason.message : "加载组合估值失败");
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载数据失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const loadHistory = async (fundCode: string, refresh = false) => {
    try {
      setHistoryLoading(true);
      setSelectedFundCode(fundCode);
      const data = await fetchFundHistory(fundCode, refresh);
      setHistory(data);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载历史净值失败");
    } finally {
      setHistoryLoading(false);
    }
  };

  const openTrendModal = async (fundCode: string) => {
    setTrendModalOpen(true);
    await loadHistory(fundCode);
  };

  const valuationByPosition = useMemo(() => {
    const map = new Map<
      string,
      {
        profit?: number | null;
        profit_rate?: number | null;
        change_rate?: number | null;
        nav_date?: string | null;
        estimated_nav?: number | null;
        unit_nav?: number | null;
      }
    >();
    for (const item of portfolio?.items ?? []) {
      const key = [item.fund_code, item.position_date ?? "", item.shares ?? 0, item.avg_cost ?? 0].join("|");
      map.set(key, {
        profit: item.profit,
        profit_rate: item.profit_rate,
        change_rate: item.change_rate,
        nav_date: item.nav_date,
        estimated_nav: item.estimated_nav,
        unit_nav: item.unit_nav,
      });
    }
    return map;
  }, [portfolio]);

  const pendingConfirmAmountTotal = useMemo(
    () => positions.reduce((sum, position) => sum + Math.max(position.pending_amount ?? 0, 0), 0),
    [positions]
  );
  const pendingSellAmountTotal = useMemo(
    () => positions.reduce((sum, position) => sum + Math.max(-(position.pending_amount ?? 0), 0), 0),
    [positions]
  );
  const pendingCount = useMemo(
    () => positions.filter((position) => Math.abs(position.pending_amount ?? 0) > 0).length,
    [positions]
  );

  const columns = useMemo(
    () => [
      {
        title: "基金",
        dataIndex: "fund_name",
        key: "fund_name",
        render: (_: unknown, record: Position) => (
          <div>
            <div>{record.fund_name || record.fund_code}</div>
            <Text type="secondary">{record.fund_code}</Text>
            {record.pending_amount > 0 ? <div className="error-line">待确认金额 {formatCurrency(record.pending_amount)}</div> : null}
            {record.pending_amount < 0 ? <div className="warning-line">待卖出金额 {formatCurrency(Math.abs(record.pending_amount))}</div> : null}
          </div>
        ),
      },
      {
        title: "持仓日期",
        dataIndex: "position_date",
        key: "position_date",
        render: (value: string) => formatDate(value),
      },
      {
        title: "金额",
        key: "amount",
        render: (_: unknown, record: Position) => formatCurrency(record.shares * record.avg_cost + (record.pending_amount ?? 0)),
      },
      {
        title: "持仓份额/单价",
        key: "position_info",
        render: (_: unknown, record: Position) => (
          <div>
            <div>{record.shares}</div>
            <div className="muted-line">{formatPrice(record.avg_cost)}</div>
          </div>
        ),
      },
      {
        title: "今日净值",
        key: "today_nav",
        render: (_: unknown, record: Position) => {
          const key = [record.fund_code, record.position_date ?? "", record.shares ?? 0, record.avg_cost ?? 0].join("|");
          const valuation = valuationByPosition.get(key);
          const changeRate = valuation?.change_rate;
          const positionAmount = record.shares * record.avg_cost + (record.pending_amount ?? 0);
          const changeAmount = changeRate === null || changeRate === undefined ? null : (positionAmount * changeRate) / 100;
          const isNavUpdated =
            valuation?.nav_date === todayDate &&
            valuation?.unit_nav !== null &&
            valuation?.unit_nav !== undefined &&
            (valuation?.estimated_nav === null || valuation?.estimated_nav === undefined);

          let color: string | undefined;
          if ((changeRate ?? 0) > 0) {
            color = "#c44536";
          } else if ((changeRate ?? 0) < 0) {
            color = "#147d64";
          }

          return (
            <div>
              <div style={{ color }}>
                {formatChangeRatePercent(changeRate)}
                {isNavUpdated ? <Text type="secondary" style={{ fontSize: 12 }}>（已更新）</Text> : null}
              </div>
              <div className="muted-line" style={{ color }}>
                {formatCurrency(changeAmount)}
              </div>
            </div>
          );
        },
      },
      {
        title: "持有收益",
        key: "profit_info",
        render: (_: unknown, record: Position) => {
          const key = [record.fund_code, record.position_date ?? "", record.shares ?? 0, record.avg_cost ?? 0].join("|");
          const valuation = valuationByPosition.get(key);
          const profit = valuation?.profit;
          const profitRate = valuation?.profit_rate;
          const color = (profit ?? 0) >= 0 ? "#c44536" : "#147d64";
          return (
            <div>
              <div style={{ color }}>{formatPercent(profitRate)}</div>
              <div className="muted-line" style={{ color }}>{formatCurrency(profit)}</div>
            </div>
          );
        },
      },
      {
        title: "操作",
        key: "actions",
        render: (_: unknown, record: Position) => (
          <Space>
            <Button size="small" icon={<LineChartOutlined />} onClick={() => void openTrendModal(record.fund_code)}>
              趋势
            </Button>
            <Button
              size="small"
              onClick={() => {
                setEditing(record);
                form.setFieldsValue({
                  fund_code: record.fund_code,
                  position_date: record.position_date,
                  trade_type: "buy",
                  amount: undefined,
                });
              }}
            >
              更新
            </Button>
            <Popconfirm
              title="删除持仓"
              description={`确认删除 ${record.fund_name || record.fund_code} 吗？`}
              okText="删除"
              cancelText="取消"
              onConfirm={() => handleDeletePosition(record)}
            >
              <Button
                size="small"
                danger
                loading={deletingId === record.id}
                icon={<DeleteOutlined />}
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [deletingId, form, todayDate, valuationByPosition]
  );

  const handleDeletePosition = async (record: Position) => {
    setDeletingId(record.id);
    try {
      await deletePosition(record.id);
      setPositions((current) => current.filter((item) => item.id !== record.id));
      if (editing?.id === record.id) {
        setEditing(null);
        form.resetFields();
        form.setFieldsValue({ position_date: defaultPositionDate });
      }
      message.success("已删除持仓");
      void loadPortfolio().catch((error) => {
        message.error(error instanceof Error ? error.message : "刷新组合估值失败");
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除持仓失败");
    } finally {
      setDeletingId(null);
    }
  };

  const handleSubmit = async (values: PositionFormValues) => {
    setSubmitting(true);
    try {
      if (editing) {
        await updatePosition(editing.id, values);
        message.success("持仓已更新");
      } else {
        const matched = positions.find((item) => item.fund_code === values.fund_code);
        if (matched) {
          await updatePosition(matched.id, values);
          message.success("持仓已更新");
        } else if (values.trade_type === "sell") {
          message.error("当前基金暂无持仓，无法卖出");
          return;
        } else {
          await createPosition(values);
          message.success("持仓已更新");
        }
      }
      form.resetFields();
      form.setFieldsValue({ position_date: defaultPositionDate, trade_type: "buy" });
      setEditing(null);
      await loadPositions();
      void loadPortfolio();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  };

  const profitPositive = (portfolio?.total_profit ?? 0) >= 0;

  return (
    <Layout className="page-shell">
      <Header className="hero-header">
        <div>
          <Text className="hero-eyebrow">FUND VALUATION MVP</Text>
          <Title className="hero-title">基金净值估算看板</Title>
          <Text className="hero-subtitle">
            录入日期、基金代码和买卖金额；净值未更新时先记录待确认金额或待卖出金额，更新后自动确认份额。
          </Text>
          <div className="hero-refresh-note">上次刷新: {lastRefreshAt ?? "--"}，点击按钮会绕过缓存强制刷新。</div>
        </div>
        <Button type="primary" size="large" icon={<ReloadOutlined />} loading={refreshing} onClick={() => void loadAll(true)}>
          刷新估值
        </Button>
      </Header>

      <Content className="page-content">
        <Spin spinning={loading} tip="正在加载基金数据">
          <Row gutter={[20, 20]}>
            <Col span={24}>
              <div className="stats-strip">
                <Card className="metric-card">
                  <Statistic title="组合总市值" value={portfolio?.total_market_value ?? 0} precision={2} prefix="¥" />
                </Card>
                <Card className="metric-card">
                  <Statistic title="组合总成本" value={portfolio?.total_cost ?? 0} precision={2} prefix="¥" />
                </Card>
                <Card className="metric-card">
                  <Statistic
                    title="组合总收益"
                    value={portfolio?.total_profit ?? 0}
                    precision={2}
                    prefix="¥"
                    valueStyle={{ color: profitPositive ? "#c44536" : "#147d64" }}
                  />
                </Card>
                <Card className="metric-card">
                  <Statistic
                    title="组合收益率"
                    value={(portfolio?.total_profit_rate ?? 0) * 100}
                    precision={2}
                    suffix="%"
                    valueStyle={{ color: profitPositive ? "#c44536" : "#147d64" }}
                  />
                </Card>
              </div>
            </Col>

            <Col xs={24} lg={16} className="top-panels-col">
              <Card className="panel-card top-chart-card top-equal-card" title="市值分布">
                <PortfolioChart items={portfolio?.items ?? []} />
              </Card>
            </Col>

            <Col xs={24} lg={8} className="top-panels-col">
              <Card className="panel-card status-card top-equal-card" title="组合状态">
                <Space direction="vertical" size={14} style={{ width: "100%" }}>
                  <div className="status-line">
                    <span className="muted-line">持仓条目</span>
                    <Text strong>{positions.length}</Text>
                  </div>
                  <div className="status-line">
                    <span className="muted-line">待处理条目</span>
                    <Text strong style={{ color: pendingCount > 0 ? "#c44536" : "#147d64" }}>
                      {pendingCount}
                    </Text>
                  </div>
                  <div className="status-line">
                    <span className="muted-line">待确认金额</span>
                    <Text strong style={{ color: pendingConfirmAmountTotal > 0 ? "#c44536" : "#147d64" }}>
                      {formatCurrency(pendingConfirmAmountTotal)}
                    </Text>
                  </div>
                  <div className="status-line">
                    <span className="muted-line">待卖出金额</span>
                    <Text strong style={{ color: pendingSellAmountTotal > 0 ? "#c44536" : "#147d64" }}>
                      {formatCurrency(pendingSellAmountTotal)}
                    </Text>
                  </div>
                  <div className="status-line">
                    <span className="muted-line">估值成功/失败</span>
                    <Text strong>
                      {portfolio?.success_count ?? 0}/{portfolio?.failed_count ?? 0}
                    </Text>
                  </div>
                </Space>
              </Card>
            </Col>
          </Row>

          <Card className="panel-card" title="持仓管理" style={{ marginTop: 20 }}>
            <Form
              form={form}
              layout="vertical"
              initialValues={{ position_date: defaultPositionDate, trade_type: "buy" }}
              onFinish={(values) => void handleSubmit(values)}
            >
              <Row gutter={16}>
                <Col xs={24} md={6}>
                  <Form.Item label="基金代码" name="fund_code" rules={[{ required: true, message: "请输入基金代码" }]}> 
                    <Input placeholder="例如 161725" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item label="持仓日期" name="position_date" rules={[{ required: true, message: "请选择持仓日期" }]}> 
                    <Input type="date" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item label="更新类型" name="trade_type" rules={[{ required: true, message: "请选择更新类型" }]}> 
                    <Radio.Group optionType="button" buttonStyle="solid">
                      <Radio.Button value="buy">买入金额</Radio.Button>
                      <Radio.Button value="sell">卖出金额</Radio.Button>
                    </Radio.Group>
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item
                    label={selectedTradeType === "sell" ? "卖出金额" : "买入金额"}
                    name="amount"
                    rules={[{ required: true, message: selectedTradeType === "sell" ? "请输入卖出金额" : "请输入买入金额" }]}
                    extra={
                      selectedTradeType === "sell"
                        ? "按当日单位净值确认卖出份额；15点前通常显示待卖出金额，15点后净值更新会自动确认。"
                        : "按当日单位净值计算份额；若当日净值未公布（通常15点后更新），暂时无法确认份额。"
                    }
                  >
                    <InputNumber style={{ width: "100%" }} min={0.01} step={100} precision={2} placeholder="例如 10000" />
                  </Form.Item>
                </Col>
              </Row>
              <Space>
                <Button type="primary" htmlType="submit" loading={submitting}>
                  更新持仓
                </Button>
                {editing ? (
                  <Button
                    onClick={() => {
                      setEditing(null);
                      form.resetFields();
                      form.setFieldsValue({ position_date: defaultPositionDate, trade_type: "buy" });
                    }}
                  >
                    取消编辑
                  </Button>
                ) : null}
              </Space>
            </Form>

            <Divider />

            <Table<Position>
              rowKey="id"
              columns={columns}
              dataSource={positions}
              pagination={false}
              locale={{ emptyText: "暂无持仓，请先录入基金代码和金额" }}
            />
          </Card>
        </Spin>
      </Content>

      <Modal
        title={history?.fund_name ? `${history.fund_name} 净值趋势` : "历史净值趋势"}
        open={trendModalOpen}
        onCancel={() => setTrendModalOpen(false)}
        width={920}
        footer={[
          <Button key="close" onClick={() => setTrendModalOpen(false)}>
            关闭
          </Button>,
          <Button
            key="refresh"
            type="primary"
            disabled={!selectedFundCode}
            loading={historyLoading}
            onClick={() => {
              if (selectedFundCode) {
                void loadHistory(selectedFundCode, true);
              }
            }}
          >
            刷新趋势
          </Button>,
        ]}
      >
        {selectedFundCode ? (
          <>
            <div className="trend-meta">
              <span>基金代码 {selectedFundCode}</span>
              <span>最近展示 {history?.points.length ?? 0} 个净值点</span>
            </div>
            <FundTrendChart history={history} loading={historyLoading} />
          </>
        ) : (
          <div className="empty-hint">从持仓表或估值明细点击“趋势”查看最近 120 个净值点。</div>
        )}
      </Modal>
    </Layout>
  );
}
