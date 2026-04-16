def _render_queue_log_preview(queue_events: list[dict]) -> None:
    preview_size = 6
    if len(queue_events) <= preview_size * 2:
        preview = queue_events
    else:
        preview = queue_events[:preview_size] + queue_events[-preview_size:]

    for event in preview:
        print(
            event["timestamp"],
            event["batch"],
            event["event"],
            event["transaction_id"],
            event["failure_reason"] or "",
        )

    if len(queue_events) > preview_size * 2:
        print("... queue log truncated ...")


def render_demo_output(demo_result: dict) -> None:
    print("Bank:", demo_result["bank"].name)
    print(
        "Initialization:",
        f"clients={len(demo_result['clients'])}",
        f"accounts={len(demo_result['accounts'])}",
        f"transactions={len(demo_result['transactions'])}",
    )
    print("Processed batches:", demo_result["processed_batches"])
    print("Queue summary:", demo_result["queue_summary"])
    print("Queue preview:")
    _render_queue_log_preview(demo_result["queue_events"])

    print("Client accounts:", demo_result["selected_client"].full_name)
    for account_info in demo_result["selected_client_accounts"]:
        print(
            " ",
            account_info["type"],
            account_info["id"],
            account_info["balance"],
            account_info["currency"],
            account_info["status"],
        )

    print("Client history:", demo_result["selected_client"].full_name)
    for entry in demo_result["selected_client_history"][:10]:
        print(
            " ",
            entry["transaction_id"],
            entry["direction"],
            entry["status"],
            entry["amount"],
            entry["currency"],
            entry["counterparty"],
            entry["failure_reason"] or "",
        )

    print("Suspicious operations for client:", len(demo_result["selected_client_suspicious"]))
    for entry in demo_result["selected_client_suspicious"][:5]:
        print(
            " ",
            entry["transaction_id"],
            entry["status"],
            entry["risk_levels"],
            entry["failure_reason"] or "",
        )

    print("Top-3 clients:")
    for index, client_data in enumerate(demo_result["top_clients"], start=1):
        print(
            f" {index}.",
            client_data["full_name"],
            client_data["total_balance"],
            client_data["base_currency"],
            f"accounts={client_data['accounts_count']}",
        )

    print("Transaction statistics:", demo_result["transaction_statistics"])
    print("Overall balance:", demo_result["overall_balance"]["amount"], demo_result["overall_balance"]["currency"])
    print("Remaining in queue:", demo_result["remaining_in_queue"])
