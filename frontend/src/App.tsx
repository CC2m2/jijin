import { DeleteOutlined, LineChartOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Col, Divider, Form, Input, InputNumber, Layout, Popconfirm, Row, Space, Spin, Statistic, Table, Tag, Typography, message } from "antd";
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
import type { FundHistory, PortfolioValuation, Position, ValuationItem } from "./types";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

type PositionFormValues = {
  fund_code: string;
  position_date: string;
  shares: number;
  avg_cost: number;
};

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

function getValuationItemKey(item: ValuationItem, index: number): string {
  return [
    item.fund_code,
    item.position_date ?? "no-date",
    item.shares,
    item.avg_cost,
    index,
  ].join("-");
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
  const [form] = Form.useForm<PositionFormValues>();
  const defaultPositionDate = new Date().toISOString().slice(0, 10);

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
        title: "份额",
        dataIndex: "shares",
        key: "shares",
      },
      {
        title: "持仓成本单价",
        dataIndex: "avg_cost",
        key: "avg_cost",
        render: (value: number) => formatPrice(value),
      },
      {
        title: "操作",
        key: "actions",
        render: (_: unknown, record: Position) => (
          <Space>
            <Button size="small" icon={<LineChartOutlined />} onClick={() => void loadHistory(record.fund_code)}>
              趋势
            </Button>
            <Button
              size="small"
              onClick={() => {
                setEditing(record);
                form.setFieldsValue({
                  fund_code: record.fund_code,
                  position_date: record.position_date,
                  shares: record.shares,
                  avg_cost: record.avg_cost,
                });
              }}
            >
              编辑
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
    [deletingId, form, message]
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
        await createPosition(values);
        message.success("持仓已新增");
      }
      form.resetFields();
      form.setFieldsValue({ position_date: defaultPositionDate });
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
            录入持仓，优先使用实时估算净值，失败时自动降级到最新公布净值。
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
            <Col xs={24} lg={16}>
              <div className="stats-grid">
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
                    valueStyle={{ color: profitPositive ? "#147d64" : "#c44536" }}
                  />
                </Card>
                <Card className="metric-card">
                  <Statistic
                    title="组合收益率"
                    value={(portfolio?.total_profit_rate ?? 0) * 100}
                    precision={2}
                    suffix="%"
                    valueStyle={{ color: profitPositive ? "#147d64" : "#c44536" }}
                  />
                </Card>
              </div>

              <Card className="panel-card" title="持仓管理">
                <Form
                  form={form}
                  layout="vertical"
                  initialValues={{ position_date: defaultPositionDate }}
                  onFinish={(values) => void handleSubmit(values)}
                >
                  <Row gutter={16}>
                    <Col xs={24} md={8}>
                      <Form.Item label="基金代码" name="fund_code" rules={[{ required: true, message: "请输入基金代码" }]}> 
                        <Input placeholder="例如 161725" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item label="持仓日期" name="position_date" rules={[{ required: true, message: "请选择持仓日期" }]}> 
                        <Input type="date" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item label="持仓份额" name="shares" rules={[{ required: true, message: "请输入持仓份额" }]}> 
                        <InputNumber style={{ width: "100%" }} min={0.0001} step={100} placeholder="例如 1000" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item label="持仓成本单价" name="avg_cost" rules={[{ required: true, message: "请输入持仓成本" }]}> 
                        <InputNumber style={{ width: "100%" }} min={0.0001} step={0.0001} precision={4} placeholder="例如 1.2356" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Space>
                    <Button type="primary" htmlType="submit" loading={submitting}>
                      {editing ? "更新持仓" : "新增持仓"}
                    </Button>
                    {editing ? (
                      <Button
                        onClick={() => {
                          setEditing(null);
                          form.resetFields();
                          form.setFieldsValue({ position_date: defaultPositionDate });
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
                  locale={{ emptyText: "暂无持仓，请先录入基金代码和仓位" }}
                />
              </Card>

              <Card
                className="panel-card"
                title={history?.fund_name ? `${history.fund_name} 净值趋势` : "历史净值趋势"}
                extra={selectedFundCode ? <Button size="small" onClick={() => void loadHistory(selectedFundCode, true)}>刷新趋势</Button> : null}
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
              </Card>
            </Col>

            <Col xs={24} lg={8}>
              <Card className="panel-card" title="市值分布">
                <PortfolioChart items={portfolio?.items ?? []} />
              </Card>

              <Card className="panel-card" title="估值明细">
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  {(portfolio?.items ?? []).map((item: ValuationItem, index) => (
                    <div key={getValuationItemKey(item, index)} className="valuation-item">
                      <div className="valuation-head">
                        <div>
                          <Text strong>{item.fund_name || item.fund_code}</Text>
                          <div className="muted-line">{item.fund_code}</div>
                          <div className="muted-line">持仓日期 {formatDate(item.position_date)}</div>
                        </div>
                        <Tag color={item.status === "success" ? "green" : "red"}>{item.status === "success" ? "成功" : "失败"}</Tag>
                      </div>
                      <div className="valuation-meta">
                        <span>市值 {formatCurrency(item.market_value)}</span>
                        <span>收益 {formatCurrency(item.profit)}</span>
                        <span>收益率 {formatPercent(item.profit_rate)}</span>
                      </div>
                      <div className="valuation-meta muted-line">
                        <span>估值 {item.estimated_nav ?? item.unit_nav ?? "--"}</span>
                        <span>涨跌 {item.change_rate !== undefined && item.change_rate !== null ? `${item.change_rate.toFixed(2)}%` : "--"}</span>
                      </div>
                      <div className="valuation-actions">
                        <Button type="link" size="small" onClick={() => void loadHistory(item.fund_code)}>
                          查看趋势
                        </Button>
                      </div>
                      {item.error ? <div className="error-line">{item.error}</div> : null}
                    </div>
                  ))}
                </Space>
              </Card>
            </Col>
          </Row>
        </Spin>
      </Content>
    </Layout>
  );
}
