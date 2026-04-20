"""
Notification service for payment plugin.

This module handles notifications related to payment events.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.plugins.advanced_auth.models import User
from ..models.payment import (
    PaymentDB,
    PaymentStatus,
    PaymentApprovalStepDB,
    PaymentRefundDB,
    RefundStatus
)

logger = logging.getLogger("kaapi.payment.notification")

class PaymentNotificationService:
    """Service for sending notifications about payment events."""
    
    @classmethod
    async def send_payment_status_notification(
        cls,
        db: Session,
        payment: PaymentDB,
        old_status: Optional[str] = None,
        message: Optional[str] = None
    ):
        """
        Send notification about payment status change.
        
        Args:
            db: Database session
            payment: Payment that changed status
            old_status: Previous status (optional)
            message: Custom message (optional)
        """
        try:
            # Get notification recipients
            recipients = await cls._get_payment_notification_recipients(db, payment)
            
            # Compose notification
            status_display = payment.status.replace("_", " ").title()
            
            if old_status:
                old_status_display = old_status.replace("_", " ").title()
                title = f"Payment #{payment.id} Status Changed: {old_status_display} → {status_display}"
            else:
                title = f"Payment #{payment.id} Status: {status_display}"
            
            if not message:
                # Default message based on status
                if payment.status == PaymentStatus.COMPLETED.value:
                    message = f"Payment of {payment.amount} {payment.currency} has been completed successfully."
                elif payment.status == PaymentStatus.FAILED.value:
                    message = f"Payment of {payment.amount} {payment.currency} has failed."
                elif payment.status == PaymentStatus.CANCELLED.value:
                    message = f"Payment of {payment.amount} {payment.currency} has been cancelled."
                elif payment.status == PaymentStatus.PROCESSING.value:
                    message = f"Payment of {payment.amount} {payment.currency} is being processed."
                elif payment.status == PaymentStatus.PENDING_APPROVAL.value:
                    message = f"Payment of {payment.amount} {payment.currency} is pending approval."
                elif payment.status == PaymentStatus.APPROVED.value:
                    message = f"Payment of {payment.amount} {payment.currency} has been approved."
                elif payment.status == PaymentStatus.REFUNDED.value:
                    message = f"Payment of {payment.amount} {payment.currency} has been fully refunded."
                elif payment.status == PaymentStatus.PARTIALLY_REFUNDED.value:
                    message = f"Payment of {payment.amount} {payment.currency} has been partially refunded ({payment.refunded_amount} {payment.currency})."
                else:
                    message = f"Payment of {payment.amount} {payment.currency} status is now {status_display}."
            
            # Create notification data
            notification_data = {
                "title": title,
                "message": message,
                "type": "payment_status",
                "payment_id": payment.id,
                "status": payment.status,
                "amount": payment.amount,
                "currency": payment.currency,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send notification using notification plugin (assumed to be integrated with Kaapi)
            await cls._send_notification(recipients, notification_data)
            
            # Send email for important status changes
            if payment.status in [
                PaymentStatus.COMPLETED.value, 
                PaymentStatus.FAILED.value, 
                PaymentStatus.CANCELLED.value,
                PaymentStatus.REFUNDED.value,
                PaymentStatus.PARTIALLY_REFUNDED.value
            ]:
                await cls._send_email_notification(recipients, notification_data)
            
            logger.info(f"Sent payment status notification for payment {payment.id}")
        
        except Exception as e:
            logger.error(f"Error sending payment status notification: {str(e)}")
    
    @classmethod
    async def send_payment_approval_notification(
        cls,
        db: Session,
        payment: PaymentDB,
        approver: User,
        approved: bool,
        comments: Optional[str] = None
    ):
        """
        Send notification about payment approval/rejection.
        
        Args:
            db: Database session
            payment: Payment that was approved/rejected
            approver: User who approved/rejected
            approved: Whether payment was approved or rejected
            comments: Approval/rejection comments
        """
        try:
            # Get notification recipients
            recipients = await cls._get_payment_notification_recipients(db, payment)
            
            # Add other approvers who haven't approved yet
            pending_approvers = await cls._get_pending_approvers(db, payment)
            if pending_approvers:
                recipients.extend(pending_approvers)
            
            # Create notification title and message
            action = "approved" if approved else "rejected"
            title = f"Payment #{payment.id} {action.title()} by {approver.full_name}"
            
            message = (
                f"Payment of {payment.amount} {payment.currency} has been {action} " +
                f"by {approver.full_name}"
            )
            
            if comments:
                message += f" with comments: '{comments}'"
            else:
                message += "."
            
            # Create notification data
            notification_data = {
                "title": title,
                "message": message,
                "type": f"payment_{action}",
                "payment_id": payment.id,
                "approver_id": approver.id,
                "approver_name": approver.full_name,
                "approved": approved,
                "comments": comments,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send notification
            await cls._send_notification(recipients, notification_data)
            
            # Send email
            await cls._send_email_notification(recipients, notification_data)
            
            logger.info(f"Sent payment {action} notification for payment {payment.id}")
        
        except Exception as e:
            logger.error(f"Error sending payment approval notification: {str(e)}")
    
    @classmethod
    async def send_payment_approval_request_notification(
        cls,
        db: Session,
        payment: PaymentDB,
        approvers: List[User]
    ):
        """
        Send notification to approvers about a payment requiring approval.
        
        Args:
            db: Database session
            payment: Payment requiring approval
            approvers: Users who need to approve
        """
        try:
            # Create notification title and message
            title = f"Payment #{payment.id} Requires Your Approval"
            message = (
                f"A payment of {payment.amount} {payment.currency} " +
                f"requires your approval."
            )
            
            # Create notification data
            notification_data = {
                "title": title,
                "message": message,
                "type": "payment_approval_request",
                "payment_id": payment.id,
                "amount": payment.amount,
                "currency": payment.currency,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send notification to approvers
            await cls._send_notification(approvers, notification_data)
            
            # Send email
            await cls._send_email_notification(approvers, notification_data)
            
            logger.info(f"Sent approval request notification for payment {payment.id}")
        
        except Exception as e:
            logger.error(f"Error sending payment approval request notification: {str(e)}")
    
    @classmethod
    async def send_refund_notification(
        cls,
        db: Session,
        refund: PaymentRefundDB,
        payment: PaymentDB,
        success: bool
    ):
        """
        Send notification about a refund.
        
        Args:
            db: Database session
            refund: Refund that was created/processed
            payment: Parent payment
            success: Whether the refund was successful
        """
        try:
            # Get notification recipients
            recipients = await cls._get_payment_notification_recipients(db, payment)
            
            # Create notification title and message
            if success:
                title = f"Refund Processed for Payment #{payment.id}"
                if refund.status == RefundStatus.COMPLETED.value:
                    status_text = "completed"
                else:
                    status_text = "initiated"
                
                message = (
                    f"A refund of {refund.amount} {refund.currency} has been {status_text} " +
                    f"for payment #{payment.id}."
                )
                
                if refund.reason:
                    message += f" Reason: {refund.reason}"
                
                if payment.is_fully_refunded:
                    message += " The payment has been fully refunded."
                else:
                    message += f" Remaining balance: {payment.amount - payment.refunded_amount} {payment.currency}."
            else:
                title = f"Refund Failed for Payment #{payment.id}"
                message = (
                    f"A refund of {refund.amount} {refund.currency} has failed " +
                    f"for payment #{payment.id}."
                )
                
                if refund.reason:
                    message += f" Refund reason: {refund.reason}"
            
            # Create notification data
            notification_data = {
                "title": title,
                "message": message,
                "type": "payment_refund",
                "payment_id": payment.id,
                "refund_id": refund.id,
                "refund_amount": refund.amount,
                "refund_currency": refund.currency,
                "refund_status": refund.status,
                "success": success,
                "is_full_refund": payment.is_fully_refunded,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send notification
            await cls._send_notification(recipients, notification_data)
            
            # Send email for refunds
            await cls._send_email_notification(recipients, notification_data)
            
            logger.info(f"Sent refund notification for payment {payment.id}, refund {refund.id}")
        
        except Exception as e:
            logger.error(f"Error sending refund notification: {str(e)}")
    
    @classmethod
    async def _get_payment_notification_recipients(
        cls,
        db: Session,
        payment: PaymentDB
    ) -> List[User]:
        """
        Get list of users who should receive notifications about a payment.
        
        Args:
            db: Database session
            payment: Payment
            
        Returns:
            List of users
        """
        recipients = []
        
        # Get creator and customer if they are different users
        from app.plugins.advanced_auth.models import User
        
        # Add payment creator
        if payment.created_by_id:
            creator = db.query(User).filter(User.id == payment.created_by_id).first()
            if creator:
                recipients.append(creator)
        
        # Add customer if different from creator
        if payment.customer_id and payment.customer_id != payment.created_by_id:
            customer = db.query(User).filter(User.id == payment.customer_id).first()
            if customer:
                recipients.append(customer)
        
        # Get users with permission to manage payments
        # This could be users with specific roles or permissions
        # For simplicity, we'll skip this for now
        
        return recipients
    
    @classmethod
    async def _get_pending_approvers(
        cls,
        db: Session,
        payment: PaymentDB
    ) -> List[User]:
        """
        Get list of users who still need to approve a payment.
        
        Args:
            db: Database session
            payment: Payment
            
        Returns:
            List of users
        """
        # Get approval steps that are still pending
        pending_steps = (
            db.query(PaymentApprovalStepDB)
            .filter(
                PaymentApprovalStepDB.payment_id == payment.id,
                PaymentApprovalStepDB.status == "pending"
            )
            .all()
        )
        
        # Get users
        from app.plugins.advanced_auth.models import User
        
        approvers = []
        for step in pending_steps:
            approver = db.query(User).filter(User.id == step.approver_id).first()
            if approver:
                approvers.append(approver)
        
        return approvers
    
    @classmethod
    async def _send_notification(cls, recipients: List[User], data: Dict[str, Any]):
        """
        Send in-app notification to users.
        
        Args:
            recipients: Users to notify
            data: Notification data
        """
        try:
            # This would be implemented using the notification plugin of Kaapi
            # For now, we just log it
            recipient_ids = [user.id for user in recipients]
            logger.info(f"Sending notification to users {recipient_ids}: {data['title']}")
            
            # In a real implementation, you would call the notification service
            # Example:
            # from kaapi.plugins.notification import send_notification
            # for user in recipients:
            #     await send_notification(user_id=user.id, data=data)
        
        except Exception as e:
            logger.error(f"Error sending in-app notification: {str(e)}")
    
    @classmethod
    async def _send_email_notification(cls, recipients: List[User], data: Dict[str, Any]):
        """
        Send email notification to users.
        
        Args:
            recipients: Users to notify
            data: Notification data
        """
        try:
            # This would be implemented using the email plugin of Kaapi
            # For now, we just log it
            recipient_emails = [user.email for user in recipients if user.email]
            logger.info(f"Sending email to {recipient_emails}: {data['title']}")
            
            # In a real implementation, you would call the email service
            # Example:
            # from kaapi.plugins.email import send_email
            # for user in recipients:
            #     if user.email:
            #         await send_email(
            #             to=user.email,
            #             subject=data['title'],
            #             body=data['message'],
            #             template="payment_notification.html",
            #             template_data=data
            #         )
        
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
