- The approval could set the tax return lock date of the company to
  the end of the period, so no journal items can be posted into a
  declared period any more.
- Journal items posted later into an approved period aren't reported:
  the statement of the next period doesn't include them and nothing
  points to them. The old module kept them as unreported moves of the
  next statement; better would be a hint on the approved statement to
  create a corrected one.
- A corrected statement doesn't refer to the statement it corrects, and
  it can be created although that statement wasn't approved.
- The XML export doesn't support these parts of the ELSTER schema yet:
  - Kz22: documents (e.g. contracts, invoices) are submitted separately
  - Kz26: don't use the SEPA direct debit mandate for this period
  - Kz29: offsetting of the refund requested, or the refund is assigned
    (only allowed with a surplus in Kz83 or for a corrected statement)
  - Kz70: date of the change from the small business regulation (§ 19
    UStG) to the standard taxation (since 2025)
  - Kz500 and Kz500_Begruendung: supplementary information on the
    statement with its reason (Kz23 before 2026)
  - Berater, Mandant and Unternehmer: a tax advisor who sends the
    statement for a client, with the name and address of the client
  - Dauerfristverlaengerung: the application for the permanent extension
    of the deadline, a declaration of its own
  - Umsatzsteuersondervorauszahlung: the declaration of the special
    advance payment (Kz38), which Kz39 deducts again in the last
    statement of the year
