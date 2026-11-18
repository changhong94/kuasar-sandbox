> PDF artifacts are no longer tracked. The preserved PDF is outside Git at
> `/home/hong/src/research/report-review-113/report/excluded-from-git/113-comprehensive-20261117/`.

# 113 六方综合基准报告（中文）

本目录发布最终 13 页报告与生成脚本。全文无历史附录；先定义 ready / print，
再说明测试批次和配置，随后按主题呈现结果。fork 和 mlink 在各表中相邻且优先排列。

- 批次 B：三语言启动，每产品每语言 1 warmup + 50 次串行，共 900 正式样本；
  native ready 与解释器 print 分别报告中位数、P95/P99、最大值。
- 批次 A：Python 完整资源套件的执行、CPU/IO、内存、存储、生命周期结果。
- 百分比为 `(fork / mlink - 1) * 100%`，从未舍入值计算；正负表示数值增加/减少。
  延迟和资源占用越低越好，吞吐越高越好。IO/存储因 RAM overlay 与持久化块盘
  语义不同不报告百分比优劣，零分母或不可用值也不计算。
- 两批数据不合并统计；A 的原始 `ready_ms` 实际是 Python print 终点，正文明确区分。

## 生成

使用 Python 3、`requirements.txt` 中的 ReportLab 和 PyMuPDF。STSong-Light
中文 CID 字体配置沿用此前报告。原始结果仍保存在 113，不把运行日志、凭据、
镜像、模板或全部原始样本重复纳入 Git。

```bash
python make_report.py   --batch-a /home/hong/src/research/sixway-aligned-20261117/results   --batch-b /home/hong/src/research/sixway-languages-20261117   --output /tmp/sixway-report
```

批次 B 根目录需有 `results/` 以及 `tools/config.json`。生成器只读取配置，
不读取配置引用的密钥文件，不访问运行中的服务。两批全部表格读取 JSON，
并验证正式样本的成功、首次尝试、销毁状态，以及 A 的完整套件验证记录。
生成 PDF 和 `manifest.json`，后者记录文件 SHA256、批次来源和章节页码。

本报告由用户授权直接发布；原始测试与归档代码在 `sixway/aligned/` 和
`sixway/hosts/113/tools/three-language-20261117/`。此次只更新报告及其生成代码，
没有重跑性能测试或修改部署。
