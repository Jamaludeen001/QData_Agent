with vw_pi1 as (
select
    distinct 
    prty_id,
    src_sys_prty_id,
    src_sys_cd
from
    party.party_identification
where
    prty_id_typ_cd = 'SLID'
),
vw_pi2 as (
select
    distinct 
    min(prty_id) as prty_id,
    src_sys_prty_id
from
    party.party_identification
where
    prty_id_typ_cd = 'SLID'
group by
    src_sys_prty_id
),
sup as (
select
    *
from
    (
    select
        distinct
        slid_id as SPVRSR_SLID,
        p.prty_id as SPVRSR_PRTY_ID,
        pers_area_desc,
        cost_ctr_num,
        cost_ctr_desc,
        SUPV_ORGUNIT_NUM,
        SUPV_ORGUNIT_DESC,
        SF_BUSINESS_UNIT_CODE,
        COMPANY_CODE,
        ATTR3_FIELD_CODE,
        ATTR3_FIELD_TEXT,
        SF_DIVISION_CODE,
        DIVISION_DESCRIPTION,
        row_number() over(partition by SPVRSR_PRTY_ID
    order by
        case
            when length(TRIM(hnc.ATTR4_FIELD_CODE)) > 0 then cast(hnc.ATTR4_FIELD_CODE as date)
            else null
        end) as seq_no
    from
        ra_spectrum.hr_non_conf hnc
    left join (
        select
            distinct 
            prty_id,
            src_sys_prty_id
        from
            party.party_identification
        where
            prty_id_typ_cd = 'SLID'
    ) as p on
        p.src_sys_prty_id = hnc.slid_id
    where
        supv_slid_id is not null
        and supv_slid_id <> ''
    )
where
    seq_no = 1
),
tar as (
select
    inac.assoc_slid,
    inac.assoc_prty_id,
    inac.assgnmnt_id,
    inac.busn_ut_cd,
    inac.intrnl_dept_grp_nm,
    inac.cost_centr_nbr,
    inac.cost_centr_desc,
    inac.lgl_entity_cd,
    inac.lgl_entity_nm,
    inac.cmpny_cd,
    inac.dept_nbr,
    inac.dept_nm,
    inac.busn_divsn_cd,
    inac.busn_divsn_desc
from
    (
    select
        assoc_slid,
        assoc_prty_id,
        assgnmnt_id,
        busn_ut_cd,
        intrnl_dept_grp_nm,
        cost_centr_nbr,
        cost_centr_desc,
        lgl_entity_cd,
        lgl_entity_nm,
        cmpny_cd,
        dept_nbr,
        dept_nm,
        busn_divsn_cd,
        busn_divsn_desc,
        row_number() over(partition by assoc_prty_id,
        assgnmnt_id
    order by
        etl_insrt_dttm desc) as rnk
    from
        party.associate assoc 
    where
        assoc_sts_cd = 'I'
        and eff_end_dttm = '9999-12-31 00:00:00.000'
    ) inac
where
    inac.rnk = 1
),
-- NEW CTE: Onshore space assignments joined from both space views
-- Only applicable for VSN (onshore) contractors
space_assign as (
select
    distinct
    asgn.slid,
    asgn.buildingid,
    asgn.mailstop,
    asgn.spacename,
    asgn.building,
    asgn.floor
from
    corporate.v_zpassignd_spaces asgn
inner join corporate.v_zpasignbl_spaces spc
    on  asgn.property    = spc.property
    and asgn.building    = spc.building
    and asgn.floor       = spc.floor
    and asgn.spacename   = spc.spacename
where
    spc.deleted  = 'N'          -- exclude deleted spaces
    and spc.status = 'Active'   -- only active spaces
)
select
    distinct 
    cast(CURRENT_DATE as varchar(10)) as EFF_STRT_DTTM,
    assignmentid as CNTRCT_NBR,
    vw_pi1.prty_id as ASSOC_PRTY_ID,
    cast(null as varchar(30)) as ETL_INTRNL_KEY,
    cast('9999-12-31 00:00:00' as timestamp) as EFF_END_DTTM,
    cast('FGCW' as varchar(10)) as SRC_SYS_CD,
    cast('NONEMP' as varchar(10)) as EMPLMT_TYP_CD,
    cast('T&M' as varchar(10)) as PRSN_CNTRCT_TYP_CD,
    cast('TIME & MATERIALS' as varchar(50)) as PRSN_CNTRCT_TYP_DESC,
    cast(null as varchar(10)) as TOT_HR_AGMT_TYP_CD,
    cast(null as varchar(50)) as TOT_HR_AGMT_TYP_DESC,
    cast(null as varchar(10)) as EMPLMT_AGMT_TYP_CD,
    cast(null as varchar(50)) as EMPLMT_AGMT_TYP_DESC,
    jobcode as PRTY_JOB_CD,
    maindocumenttitle as PRTY_JOB_TITL_NM,
    cast(null as varchar(100)) as PRTY_JOB_CLSFCTN_DESC,
    cast(null as varchar(20)) as PRTY_JOB_LVL_CD,
    cast(null as varchar(30)) as EMPL_INTRNL_POSTN_NBR,
    businessunitpsapa as BUSN_UT_NM,
    cast(null as varchar(254)) as BUSN_UT_DESC,
    cast(null as varchar(100)) as INTRNL_DEPT_NM,
    cast(null as char(1)) as SPVRSR_IND,
    left(ponumber, 15) as PURCH_ORDR_NBR,
    cast(null as varchar(75)) as VNDR_PURCH_ORDR,
    cast(null as varchar(75)) as REQSTN_ID,
    case
        when length(TRIM(workerregistrationdate)) > 0 then TO_DATE(TO_CHAR(TO_DATE(cw.workerregistrationdate, 'MM/DD/YYYY HH:MI AM'), 'YYYY-MM-DD'), 'YYYY-MM-DD')
        else null
    end as WRKR_REGN_DT,
    cast(null as varchar(100)) as ASSGNMNT_REVSN_OWNR_NM,
    cast(null as varchar(50)) as SRC_SYS_PRTY_USR_NM,
    cast(null as varchar(100)) as REQSTN_TITL_NM,
    whichnercaccessisneeded as WHICH_NERC_ACCESS_NEEDED_DESC,
    left(physicalaccessrequired, 1) as PRTY_PHYSCL_ACCSS_REQD_IND,
    cast(null as char(1)) as PRTY_CYBR_NTWRK_ACCESS_REQD_IND,
    left(isnerccipunescortedphysicalorcyberaccessrequiredforthisassignment, 1) as NERC_ACCESS_NEEDED_IND,
    left(willdrivingberequiredaspartofpositiondutieswork, 1) as DRVNG_REQD_IND,
    cast(null as date) as WRKR_ERLST_STRT_DT,
    case
        when length(TRIM(originalstartdate)) > 0 then cast(originalstartdate as date)
        else null
    end as WRKR_ORGNL_STRT_DT,
    cast(null as numeric(18, 6)) as MAX_EXPNS_AMT,
    cast(null as varchar(100)) as WRKR_BUYR_NM,
    cast(null as varchar(100)) as WRKR_SUPLR_NM,
    cast(null as varchar(100)) as SRVC_TYP_DESC,
    autoinvoicetype as AUTO_INVC_TYP_DESC,
    left(approved2yeartenureexceptionyesno, 1) as APPRVD_2_YR_TNR_EXCPTN_IND,
    assignmentdetails as ASSGNMNT_DTLS_TXT,
    pleaserateyourexperienceworkingwiththissuppliertofillthisrequirement as INTRNL_SUPLR_EXPRN_RATG_TXT,
    cast(null as integer) as GNRTN_ARGUMENT_NBR,
    UPPER(workerslid) as ASSOC_SLID,
    case
        when length(TRIM(assignmentstartdate)) > 0 then cast(assignmentstartdate as date)
        else null
    end as ASSGNMNT_STRT_DT,
    case
        when length(TRIM(assignmentenddate)) > 0 then cast(assignmentenddate as date)
        else null
    end as ASSGNMNT_END_DT,
    cast(null as varchar(50)) as ASSOC_TYP_DESC,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.pers_area_desc
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.intrnl_dept_grp_nm is not null
            and tar.intrnl_dept_grp_nm != '') then tar.intrnl_dept_grp_nm
        else sup.pers_area_desc
    end as intrnl_dept_grp_nm,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.cost_ctr_num
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.COST_CENTR_NBR is not null
            and tar.COST_CENTR_NBR != '') then tar.COST_CENTR_NBR
        else sup.cost_ctr_num
    end as COST_CENTR_NBR,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.cost_ctr_desc
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.COST_CENTR_DESC is not null
            and tar.COST_CENTR_DESC != '') then tar.COST_CENTR_DESC
        else sup.cost_ctr_desc
    end as COST_CENTR_DESC,
    -- MAIL_STOP_TXT: VSN (onshore) → from space views; VSF (offshore) → null
    case
        when UPPER(cw.headcountcompanycode) = 'VSN' then sp.mailstop
        else null
    end as MAIL_STOP_TXT,
    cast(null as char(1)) as WRKR_NEEDS_SEAT_IND,
    sapvendor as SAP_VNDR_ID,
    cast(null as varchar(10)) as INTRNL_DEPT_NBR,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.SUPV_ORGUNIT_NUM
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.LGL_ENTITY_CD is not null
            and tar.LGL_ENTITY_CD != '') then tar.LGL_ENTITY_CD
        else sup.SUPV_ORGUNIT_NUM
    end as LGL_ENTITY_CD,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.SUPV_ORGUNIT_DESC
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.LGL_ENTITY_NM is not null
            and tar.LGL_ENTITY_NM != '') then tar.LGL_ENTITY_NM
        else sup.SUPV_ORGUNIT_DESC
    end as LGL_ENTITY_NM,
    defaultbusinessunit as DFLT_BUSN_UT_NM,
    cast(null as int) as CMPNY_ID,
    cast(null as varchar(10)) as ASSOC_TYP_CD,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.SF_BUSINESS_UNIT_CODE
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.BUSN_UT_CD is not null
            and tar.BUSN_UT_CD != '') then tar.BUSN_UT_CD
        else sup.SF_BUSINESS_UNIT_CODE
    end as BUSN_UT_CD,
    cast(null as varchar(10)) as CAREER_FMLY_CD,
    cast(null as varchar(100)) as CAREER_FMLY_DESC,
    left(cw.headcountcompanycode, 4) as CMPNY_CD,
    cast(null as varchar(25)) as CMPNY_DESC,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.ATTR3_FIELD_CODE
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.DEPT_NBR is not null
            and tar.DEPT_NBR != '') then tar.DEPT_NBR
        else sup.ATTR3_FIELD_CODE
    end as DEPT_NBR,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.ATTR3_FIELD_TEXT
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.DEPT_NM is not null
            and tar.DEPT_NM != '') then tar.DEPT_NM
        else sup.ATTR3_FIELD_TEXT
    end as DEPT_NM,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.SF_DIVISION_CODE
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.BUSN_DIVSN_CD is not null
            and tar.BUSN_DIVSN_CD != '') then tar.BUSN_DIVSN_CD
        else sup.SF_DIVISION_CODE
    end as BUSN_DIVSN_CD,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then sup.DIVISION_DESCRIPTION
        when upper(cw.workerstatus) = 'CLOSED'
        and (tar.BUSN_DIVSN_DESC is not null
            and tar.BUSN_DIVSN_DESC != '') then tar.BUSN_DIVSN_DESC
        else sup.DIVISION_DESCRIPTION
    end as BUSN_DIVSN_DESC,
    cast(null as varchar(10)) as FINCL_GRPING_CD,
    cast(null as varchar(100)) as FINCL_GRPING_DESC,
    cast(null as varchar(10)) as INTRNL_DEPT_GRP_NBR,
    cast(null as varchar(10)) as JOB_FMLY_CD,
    cast(null as varchar(100)) as JOB_FMLY_DESC,
    cast(null as varchar(10)) as ORG_UT_NBR,
    cast(null as varchar(100)) as ORG_UT_DESC,
    networkaccessmethod as NTWRK_ACCSS_MTHD_DESC,
    masterworkerrecordid as MSTR_WRKR_ID,
    cast(null as varchar(5)) as ASSOC_GRP_CD,
    cast(null as varchar(10)) as ASSOC_SUB_GRP_CD,
    cast(null as varchar(50)) as EMPL_NBR,
    cast(null as numeric(18, 6)) as BILL_RATE_DBL_TME_AMT,
    cast(null as numeric(18, 6)) as BILL_RATE_OVER_TME_AMT,
    cast(null as numeric(18, 6)) as BILL_RATE_OVER_TME_STRGT_TME_AMT,
    cast(null as numeric(18, 6)) as PRTY_BILL_RATE_STRGT_TME_AMT,
    cast(null as numeric(18, 6)) as PRTY_PAY_RATE_STRGT_TME_AMT,
    cast(null as numeric(18, 6)) as PAY_RATE_DBL_TME_AMT,
    cast(null as numeric(18, 6)) as PAY_RATE_OVER_TME_AMT,
    cast(null as numeric(18, 6)) as PAY_RATE_OVER_TME_STRGT_TME_AMT,
    cw.securityid as SRC_SYS_SCRTY_ID,
    cast(null as varchar(10)) as DIRECT_REPORTS_IND,
    cast(null as varchar(10)) as DIVSN_CD,
    cast(null as varchar(10)) as DIVSN_DESC,
    cast(null as varchar(10)) as EMPLMT_STS_CD,
    cast('Non-Employee' as varchar(20)) as EMPLMT_TYP_DESC,
    left(isthiscandidateaw2ora1099independentcontractor, 3) as W_2_OR_1099_INDPNDNT_CNTRCTR_IND,
    workerid as ASSGNMNT_ID,
    vw_pi2.prty_id as SPVRSR_PRTY_ID,
    slid as SPVRSR_SLID,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then 'A'
        when UPPER(cw.workerstatus) = 'CLOSED' then 'I'
    end as ASSOC_STS_CD,
    case
        when UPPER(cw.workerstatus) = 'OPEN' then 'Active'
        when UPPER(cw.workerstatus) = 'CLOSED' then 'Inactive'
    end as ASSOC_STS_DESC,
    'CW' as SOURCE_TABLE_NAME,
    '1900-01-01 00:00:00' as SOURCE_TABLE_TIMESTAMP,
    cast(null as varchar(100)) as ALIAS_NM,
    cast(null as varchar(50)) as ROOM_NBR,
    cast(null as varchar(10)) as SAP_BUSN_UT_CD,
    cast(null as varchar(10)) as SAP_DIVSN_CD,
    cast(null as varchar(20)) as SAP_FINCL_GRPING_CD,
    cast(null as varchar(20)) as MOPR_GRP_CD,
    cast(null as varchar(100)) as MOPR_GRP_DESC,
    -- SEAT_NUM: VSN → spacename from space views; VSF → null
    case
        when UPPER(cw.headcountcompanycode) = 'VSN' then sp.spacename
        else null
    end as SEAT_NUM,
    cast(null as varchar(200)) as position_title,
    -- prnt_bldng: VSN → buildingid from space views; VSF → null
    case
        when UPPER(cw.headcountcompanycode) = 'VSN' then sp.buildingid
        else null
    end as prnt_bldng,
    -- prnt_flr: VSN → floor from space views; VSF → null
    case
        when UPPER(cw.headcountcompanycode) = 'VSN' then sp.floor
        else null
    end as prnt_flr
from
    ra_spectrum.contingent_worker cw
inner join vw_pi1 as vw_pi1 on
    vw_pi1.src_sys_prty_id = UPPER(cw.workerslid)
left join vw_pi2 as vw_pi2 on
    vw_pi2.src_sys_prty_id = cw.slid
left join sup as sup on
    sup.SPVRSR_PRTY_ID = vw_pi2.prty_id
left join tar as tar on
    tar.assoc_slid = cw.workerslid
    and tar.assgnmnt_id = cw.workerid
-- NEW JOIN: only for onshore (VSN) contractors
left join space_assign sp on
    UPPER(sp.slid) = UPPER(cw.workerslid)
    and UPPER(cw.headcountcompanycode) = 'VSN'
where
    UPPER(cw.workerstatus) in ('OPEN', 'CLOSED')
    and (UPPER(cw.workerslid) <> '' or length(cw.workerslid) != 0)
    and UPPER(cw.workerslid) not like ('TO BE POPULATED VIA INTERFACE%')
    and cw.workerslid is not null
    and trim(cw.assignmentstartdate) <> ''
    and workerid is not null
