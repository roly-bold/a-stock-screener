import argparse
import json
import os

from data_fetcher import get_stock_list, get_stock_hist, load_csv, scan_all_stocks
from strategy import screen_stock


def run_full_scan(days=120, delay=0.3, output="results.json"):
    """全市场扫描"""
    print("获取股票列表...")
    stock_list = get_stock_list()
    print(f"共 {len(stock_list)} 只股票待扫描")

    print("开始扫描...")
    stock_data = scan_all_stocks(stock_list, days=days, delay=delay)

    print("执行选股策略...")
    results = []
    for code, (name, df) in stock_data.items():
        signals = screen_stock(df)
        for s in signals:
            s["code"] = code
            s["name"] = name
        results.extend(signals)

    results.sort(key=lambda x: x["entry_date"], reverse=True)
    _save_results(results, output)
    print(f"\n扫描完成，共发现 {len(results)} 个信号，结果保存至 {output}")
    print_results(results)
    return results


def run_single(code, days=120):
    """单只股票检测"""
    print(f"检测股票 {code}...")
    df = get_stock_hist(code, days=days)
    if df.empty:
        print("未获取到数据，请检查网络或 token 配置")
        return []

    signals = screen_stock(df)
    if signals:
        for s in signals:
            s["code"] = code
            s["name"] = ""
        print(f"发现 {len(signals)} 个信号:")
        print_results(signals)
    else:
        print("未发现符合条件的信号")
    return signals


def run_csv(path, days=120):
    """从CSV文件检测"""
    print(f"从 {path} 加载数据...")
    df = load_csv(path, days=days)
    print(f"加载 {len(df)} 行数据")

    signals = screen_stock(df)
    if signals:
        print(f"发现 {len(signals)} 个信号:")
        print_results(signals)
    else:
        print("未发现符合条件的信号")
    return signals


def _save_results(results, output):
    clean = []
    for r in results:
        clean.append({k: (float(v) if hasattr(v, "item") else v) for k, v in r.items()})
    with open(output, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def print_results(results):
    if not results:
        return
    print(f"\n{'代码':<8} {'名称':<10} {'起爆日':<12} {'Pivot高':<10} "
          f"{'整理结束':<12} {'突破日':<12} {'买入价':<10} "
          f"{'最新价':<10} {'止损':<4}")
    print("-" * 95)
    for r in results:
        print(f"{r.get('code',''):<8} {r.get('name',''):<10} {r['breakout_date']:<12} "
              f"{r['pivot_high']:<10} {r['consolidation_end']:<12} "
              f"{r['entry_date']:<12} {r['entry_price']:<10} "
              f"{r['latest_close']:<10} {'是' if r['exit_triggered'] else '否':<4}")


def setup_config(token, api_url="http://tushare.xyz"):
    """配置 tushare token"""
    config = {"tushare_token": token, "tushare_api_url": api_url}
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"配置已保存至 {config_path}")

    from data_fetcher import _get_pro
    _get_pro()
    print("连接测试成功!")


def main():
    parser = argparse.ArgumentParser(description="A股量化选股 - 二次突破策略")
    parser.add_argument("--code", type=str, help="单只股票代码（如 000001）")
    parser.add_argument("--csv", type=str, help="从CSV文件加载数据")
    parser.add_argument("--days", type=int, default=120, help="回溯天数（默认120）")
    parser.add_argument("--delay", type=float, default=0.3, help="请求间隔秒数（默认0.3）")
    parser.add_argument("--output", type=str, default="results.json", help="输出文件名")
    parser.add_argument("--setup", type=str, metavar="TOKEN", help="配置 tushare token")
    args = parser.parse_args()

    if args.setup:
        setup_config(args.setup)
        return

    if args.csv:
        run_csv(args.csv, days=args.days)
    elif args.code:
        run_single(args.code, days=args.days)
    else:
        run_full_scan(days=args.days, delay=args.delay, output=args.output)


if __name__ == "__main__":
    main()
