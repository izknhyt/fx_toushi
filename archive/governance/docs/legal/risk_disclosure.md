# リスク開示文書（ドラフト）

> **版数**: v0.1
> **最終更新日**: 2025-03-10
> **最終更新者**: Compliance Advisor (Doc Maintainer)

## 1. 目的
- Paper/Pilot運用に参加する関係者へ、戦略のリスク要因・損失可能性・運用制限を明示する。
- AC-40/AC-43で求められるリスク同意プロセスのベース文面として利用する。

## 2. 適用範囲
- M1.1以降のResearch Guild・Opsチーム・ステークホルダー向けリスク開示。
- Paper運用ログ`logs/audit/risk_consent_*.jsonl`に紐付く文面。

## 3. 暫定構成案
1. **総論**: 投資リスク・流動性リスク・スプレッド拡大リスク・システム障害リスクの概要。
2. **戦略固有のリスク**: `m1_baseline_ma_rsi`のパラメータ依存性、バックテスト限界、データリビジョンリスク。
3. **運用制限**: 取引時間帯、Kill Switch/Reduce-Only条件、レバレッジ上限。
4. **データ利用について**: Dukascopy等の第三者データ利用、著作権・ライセンスへの準拠。
5. **同意手続き**: `RiskDisclosureService`が収集する署名/承認フローの説明。
6. **更新手順**: 四半期レビュー、Runbookとの連携、文面バージョンの管理。

## 4. 今後のToDo
- Compliance Advisorが法務レビューを実施し、正式文面を作成。
- `config/compliance/risk_disclosure.yaml`に文面パスと有効期限を登録。
- 完成後に版数をv1.0へ更新し、要件定義・基本設計のRunbook参照を更新。
