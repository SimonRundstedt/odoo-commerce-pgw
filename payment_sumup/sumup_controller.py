# -*- coding: utf-8 -*-
##############################################################################
#
# Odoo, Open Source Enterprise Management Solution, third party addon
# Copyright (C) 2004-2017 Vertel AB (<http://vertel.se>).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning
from openerp import http
from openerp.http import request
#import werkzeug


import logging
_logger = logging.getLogger(__name__)

class SumupController(http.Controller):

    @http.route(['/payment/sumup/verify'], type='http', auth='public', method='POST', website=True)
    def auth_payment(self, **post):
        """
        Check card information with SumUP, sends error to /payment/sumup/initPayment 
        or update status on order
        """
        _logger.warn(post)
        ref = post.get('reference')
        if not ref:
            _logger.warn("Error in Sumup return. No reference found!")
            return request.render('payment_sumup.payment_form', {'reference': tx.reference,'error_message':_('No order reference found!') })

    @http.route(['/payment/sumup/initPayment'], type='http', auth='public', method='POST', website=True)
    def init_payment(self, **post):
        """
        Contact SumUp and redirect customer.
        """
        _logger.warn('Sale trasactionm id %s' % request.session.get('sale_transaction_id', []))
        tx = request.env['payment.transaction'].sudo().browse(request.session.get('sale_transaction_id', []))
        _logger.warn(tx)
        return request.render('payment_sumup.payment_form', {'reference': tx})


        tx = request.env['payment.transaction'].sudo().browse(request.session.get('sale_transaction_id', []))
        if not tx:
            werkzeug.utils.redirect('/shop/payment', 302)
        service = SumUp(
            merchant_number=tx.acquirer_id.SumUp_account_nr,
            encryption_key=tx.acquirer_id.SumUp_key,
            production=tx.acquirer_id.environment == 'prod')
        response = service.initialize(
            purchaseOperation = 'SALE',
            price = int(tx.amount * 100),
            currency = tx.currency_id.name,
            vat =int( (tx.sale_order_id.amount_tax / tx.sale_order_id.amount_untaxed) * 100),
            orderID = tx.reference,
            productNumber = tx.reference,
            description = 'Web order',
            clientIPAddress = request.httprequest.remote_addr,
            clientIdentifier = 'USERAGENT=%s' % request.httprequest.user_agent.string,
            additionalValues = 'RESPONSIVE=1',
            returnUrl = '%s/payment/SumUp/verify' % request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            view = tx.acquirer_id.SumUp_view,
            cancelUrl = '%s/shop/payment' % request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
        )
        # code              String(128)     Obsolete parameter, check errorCode.
        # errorCode         String          Indicates the result of the request. Returns OK if request is successful.
        # description       String(512)     A literal description explaining the result. Returns OK if request is successful.
        # paramName         String          Returns the name of the parameter that contains invalid data.
        # thirdPartyError   String          Returns the error code received from third party (not available for all payment methods).
        # orderRef          String(32)      This parameter is only returned if the parameter is successful, and returns a 32bit, hexadecimal value (Guid) identifying the orderRef.Example: 8e96e163291c45f7bc3ee998d3a8939c
        # sessionRef        String          Obsolete parameter.
        # redirectUrl       String          Dynamic URL to send the end user to, when using redirect model.
        if response:
            _logger.warn(response)
            status = response.get('status')
            if not status:
                _logger.warn("Error when contacting SumUp! Didn't get a status.\n%s" % response)
                return 'Error when contacting SumUp!'
            tx.state_message = status.get('description')
            if not status.get('errorCode'):
                _logger.warn("Error when contacting SumUp! Didn't get an error code.\n%s" % response)
                return 'Error when contacting SumUp!'
            if status.get('errorCode') != 'OK':
                _logger.warn("Error when contacting SumUp! Status not OK.\n%s" % response)
                return 'Error when contacting SumUp!'
            if not response.get('orderRef'):
                _logger.warn("Error when contacting SumUp! Didn't get an order reference.\n%s" % response)
                return 'Error when contacting SumUp!'
            if not response.get('redirectUrl'):
                _logger.warn("Error when contacting SumUp! Didn't get a redirect url.\n%s" % response)
                return 'Error when contacting SumUp!'
            tx.acquirer_reference = response.get('orderRef')
            return werkzeug.utils.redirect(response.get('redirectUrl'), 302)
        _logger.warn("Error when contacting SumUp! Didn't get a response.\n%s" % response)
        return 'Error when contacting SumUp!'
