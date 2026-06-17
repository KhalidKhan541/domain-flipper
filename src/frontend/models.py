from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class Domain(BaseModel):
    id: Optional[int] = None
    domain_name: Optional[str] = None
    price: Optional[float] = None
    auction_end_date: Optional[date] = None
    registrar: Optional[str] = None
    tld: Optional[str] = None
    source: Optional[str] = None
    dr: Optional[int] = None
    referring_domains: Optional[int] = None
    domain_age: Optional[int] = None
    category: Optional[str] = None
    final_score: Optional[float] = None
    opportunity_grade: Optional[str] = None
    trust_score: Optional[float] = None
    seo_score: Optional[float] = None
    commercial_score: Optional[float] = None
    cleanliness_score: Optional[float] = None
    broker_score: Optional[float] = None
    broker_grade: Optional[str] = None
    estimated_value: Optional[float] = None
    commission_amount: Optional[float] = None
    buyer_lead_count: Optional[int] = None
    marketplace_listings: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Purchase(BaseModel):
    id: Optional[int] = None
    domain_name: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[date] = None
    sale_price: Optional[float] = None
    sale_date: Optional[date] = None
    holding_days: Optional[int] = None
    roi: Optional[float] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class Outreach(BaseModel):
    id: Optional[int] = None
    domain_name: Optional[str] = None
    lead_type: Optional[str] = None
    company: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_linkedin: Optional[str] = None
    template_subject: Optional[str] = None
    template_body: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CommissionAgreement(BaseModel):
    id: Optional[int] = None
    domain_name: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_company: Optional[str] = None
    seller_name: Optional[str] = None
    seller_company: Optional[str] = None
    commission_amount: Optional[float] = None
    commission_rate: Optional[float] = None
    estimated_value: Optional[float] = None
    agreement_path: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SeoAnalysis(BaseModel):
    dr: Optional[int] = None
    referring_domains: Optional[int] = None
    domain_age: Optional[int] = None
    seo_score: Optional[float] = None


class HistoryAnalysis(BaseModel):
    domain_age: Optional[int] = None
    created_at: Optional[datetime] = None
    registrar: Optional[str] = None


class CommercialAnalysis(BaseModel):
    commercial_score: Optional[float] = None
    estimated_value: Optional[float] = None
    commission_amount: Optional[float] = None
    buyer_lead_count: Optional[int] = None
    marketplace_listings: Optional[str] = None


class BrokerAnalysis(BaseModel):
    broker_score: Optional[float] = None
    broker_grade: Optional[str] = None
    opportunity_grade: Optional[str] = None


class DomainAnalysis(BaseModel):
    domain: Optional[Domain] = None
    seo: Optional[SeoAnalysis] = None
    history: Optional[HistoryAnalysis] = None
    commercial: Optional[CommercialAnalysis] = None
    broker: Optional[BrokerAnalysis] = None
    final_score: Optional[float] = None
    trust_score: Optional[float] = None
    cleanliness_score: Optional[float] = None
    reason: Optional[str] = None

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_today: Optional[int] = 0
    avg_score: Optional[float] = 0.0
    top_grade: Optional[str] = None
    total_leads: Optional[int] = 0
    leads_by_status: Optional[dict[str, int]] = Field(default_factory=dict)
    leads_by_type: Optional[dict[str, int]] = Field(default_factory=dict)
