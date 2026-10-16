# Storefront operations

## Catalog and merchandising
- In Django admin, upload category images and create active Store banners. Banners may target a category; position controls their order.
- Product specifications are key/value text and size guides are supplied by sellers or admins. Content edits require normal approval.
- Original price is optional and must be at least the selling price. Set a genuine original price; the storefront calculates the displayed discount.
- Review comments are public without customer email or identity.

## Delivery and orders
- Configure Delivery areas by six-digit pincode and minimum/maximum estimated days. Unconfigured pincodes are not promised delivery; checkout is not restricted by this informational checker.
- Sellers enter carrier, tracking number and an HTTPS carrier URL from Orders. Tracking is manual; carrier webhook integration is not configured.
- Marking a shipment delivered records its delivery date. Delivered/dispatched shipments cannot move backwards.
- Customers request cancellation before dispatch, eligible returns after delivery, or refund enquiries from My orders.
- Requests appear in Django admin and seller order data. Admin reviews status and writes a response; responses appear in the customer's order history.
- Approving a request is a review decision, not an automatic financial transaction. Process actual refunds with the existing seller Razorpay refund workflow. Do not mark requests resolved until fulfillment/payment work is complete.
- New order items preserve the return policy accepted at purchase. Older items use the current policy because a historical snapshot does not exist.

## Coupons
- Coupons are created by admins for one seller and require explicit activation, dates and a 1–95% discount. The minimum applies to that seller's eligible subtotal.
- Discounts are seller-funded. Net item prices are recorded on the order, so seller totals and refund limits use the discounted prices.
- Preview and checkout both calculate money on the server in integer paise, rounding each discounted unit to the nearest paisa (half up).
- Pending payment orders retain their original coupon; changing it requires resolving the pending payment first.
- Usage limits, per-customer redemption limits, stacking and platform-funded subsidies are not included.

## Support
- Customers submit private tickets in Help centre and read responses there. Admin responds through Support tickets.
- No automated email or guaranteed response-time claim is made.

## Deployment and external setup
- Additive migrations run through the existing Render startup command.
- Live Razorpay/email credentials remain required before live payments and outbound messages can work.
- Populate genuine catalog photography, product specifications, size guides, serviceable delivery areas and approved promotions. Do not invent delivery promises or discount amounts.
- Language localization and automated carrier integration remain separate enhancements.
